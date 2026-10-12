#!/usr/bin/env python3
"""构建工作流的本地静态检查（不需要联网、不需要 GitHub）。

本仓库的 .github/workflows/build.yml 里内联了大量 bash，而 GitHub 只在
workflow 被触发时才会执行它们 —— 一次语法错误就要赔上「push → 等 runner →
看日志」的一整轮。这个脚本把那一轮提前到本地几秒钟。

做三件事：
  1. YAML 可解析
  2. 每个 run 块 `bash -n` 语法检查（先把 ${{ ... }} 替换成占位符，
     因为那些表达式在运行时才会被 GitHub 展开）
  3. 每个 run 块引用的 ${VAR} 都能找到来源（step env / job env / 工作流 env /
     脚本内赋值 / for 与 read 变量），避免 set -u 下踩未定义变量

用法：
    python tools/check-workflow.py [workflow.yml ...]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:
    sys.exit("需要 PyYAML：pip install pyyaml")

EXPR = re.compile(r"\$\{\{[^}]*\}\}")
# ${NAME} / ${NAME:-默认} / ${NAME%%pattern} 都只关心头部的变量名
REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)[^}]*\}|\$([A-Za-z_][A-Za-z0-9_]*)")
DEF = re.compile(r"(?:^|[\s;(|&{])([A-Za-z_][A-Za-z0-9_]*)=(?!=)")
FOR_VAR = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\b")
# `read -r a b c` 会一次定义多个变量，要全部收下
READ_LINE = re.compile(r"\bread\s+(?:-\w+\s+)*([^\n;|&]+)")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# bash / GitHub 自带，不必在 env 里声明
BUILTIN = {
    "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "GITHUB_ENV", "GITHUB_SHA",
    "GITHUB_REPOSITORY", "GITHUB_ACTOR", "GITHUB_REF", "GITHUB_WORKSPACE",
    "HOME", "PATH", "PWD", "RANDOM", "IFS", "OLDPWD", "SHELL", "USER", "TMPDIR",
}


def subst(text: str) -> str:
    return EXPR.sub("GHEXPR", text)


def main(argv: list[str]) -> int:
    files = argv[1:] or [".github/workflows/build.yml"]
    total = bad = 0

    for path in files:
        if not os.path.isfile(path):
            print("!! 文件不存在：%s" % path)
            bad += 1
            continue

        print("=" * 72)
        print("# %s" % path)
        try:
            wf = yaml.safe_load(open(path, encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print("!! YAML 解析失败：%s" % exc)
            bad += 1
            continue
        print("  YAML 解析 OK")

        wf_env = set(wf.get("env") or {})
        for jname, job in (wf.get("jobs") or {}).items():
            job_env = set(job.get("env") or {})
            for i, step in enumerate(job.get("steps") or [], 1):
                if "run" not in step:
                    continue
                total += 1
                label = step.get("name") or step.get("uses") or ("step%d" % i)
                script = subst(step["run"])
                if not script.endswith("\n"):
                    script += "\n"

                problems: list[str] = []

                # --- 2) bash 语法
                tmp = os.path.join(tempfile.gettempdir(),
                                   "wf_%s_%d_%d.sh" % (jname, i, os.getpid()))
                with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(script)
                res = subprocess.run(["bash", "-n", tmp], capture_output=True, text=True)
                if res.returncode != 0:
                    problems.append("bash 语法：" + " ".join(res.stderr.split()))
                os.remove(tmp)

                # --- 3) 变量来源
                defined = set(DEF.findall(script))
                defined |= set(FOR_VAR.findall(script))
                for line in READ_LINE.findall(script):
                    defined |= {t for t in line.split() if IDENT.match(t)}
                known = defined | set(step.get("env") or {}) | job_env | wf_env | BUILTIN
                used = {m.group(1) or m.group(2) for m in REF.finditer(script)}
                missing = sorted(v for v in used if v not in known)
                if missing:
                    problems.append("未定义变量：" + ", ".join(missing))

                tag = "OK  " if not problems else "FAIL"
                if problems:
                    bad += 1
                print("  %s %-9s %s" % (tag, jname, label[:46]))
                for p in problems:
                    print("        %s" % p)

    print("=" * 72)
    print("共 %d 个 run 块，问题 %d 个" % (total, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
