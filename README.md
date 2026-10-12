# cloudflared · 极简多架构镜像

> 从 [cloudflare/cloudflared](https://github.com/cloudflare/cloudflared) 上游源码自编译。
> `scratch` 基础层、strip 后二进制、5 架构合一，拉取约 9 MB。

```
ghcr.io/wliky/cloudflared:latest
```

---

## 为什么用它

| | 官方镜像 | 本镜像 |
|---|---|---|
| 基础层 | distroless（带 shell 与工具链） | **scratch**，只有二进制 + CA + LICENSE |
| 二进制 | 上游 `LINK_FLAGS` 为空，**未 strip** | `-s -w -buildid=`，**体积小约 31%** |
| `arm/v7` | ✗ 不提供 | ✓ |
| 拉取体积 | 40 MB+ | **约 9 MB** |
| 运行身份 | nonroot | nonroot（65532:65532） |

架构：`amd64` · `arm64` · `arm/v7` · `arm/v6` · `386` —— 合在**一个 manifest list** 里，
拉同一个 tag 即可，Docker 自动挑对的那份。

## 用法

```yaml
services:
  cloudflared:
    image: ghcr.io/wliky/cloudflared:latest
    container_name: cloudflared
    restart: unless-stopped
    network_mode: host
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
    command: tunnel run
```

`TUNNEL_TOKEN` 是 cloudflared 的**原生环境变量**，无需任何 entrypoint 脚本包装。
也支持 `TUNNEL_TOKEN_FILE`，或挂载凭据文件走 named tunnel。

完整示例见 [`docker-compose.example.yml`](./docker-compose.example.yml)。

## 标签

| tag | 用途 |
|---|---|
| `:2026.10.0` 等上游版本号 | 钉版本，**生产推荐** |
| `:latest` | 上游最新 release，**永远指向标准版** |
| `:sha-<7位>` | 对应构建提交，便于回溯 |
| `:upx` · `:<版本>-upx` | UPX 压缩版，仅手动触发时产出 |

> **关于 UPX**：二进制压到约 1/3（armv7 24.2 → 8.3 MiB），但镜像层本身就是 gzip，
> 所以**拉取体积只省 5~12%** —— 它省的是磁盘，不是带宽。因此 `:latest` 从不指向 UPX。

## 镜像内容

```
/cloudflared                         静态二进制（CGO_ENABLED=0，已 strip）
/etc/ssl/certs/ca-certificates.crt   Mozilla CA 根证书
/etc/passwd · /etc/group             nonroot 65532 各一行
/LICENSE                             Apache-2.0 原文
```

Entrypoint 与官方一致（`/cloudflared --no-autoupdate`，默认 `tunnel run`），
换镜像只需改 `image:` 一行。镜像内**没有 shell**，排障请用 `docker logs`。

## 构建

`Dockerfile` 里**没有任何 `RUN`** —— 二进制由 CI 在 runner 上交叉编译，镜像构建只是几次 `COPY`，
因此多架构构建**不需要 QEMU**。

```
resolve ─→ build（矩阵 × 5 架构，--push-by-digest）─→ merge（imagetools create → manifest list）
```

**每月 10 日**自动检查上游新版本，GHCR 已有对应 tag 就跳过。也可手动触发：

```bash
gh workflow run build.yml -f force=true          # 重建最新版
gh workflow run build.yml -f version=2026.10.0   # 指定版本
gh workflow run build.yml -f upx=true            # 额外产出 UPX 版
```

改 workflow 前建议先本地自检：`pip install pyyaml && python tools/check-workflow.py`
（校验 YAML 可解析、每个 `run` 块的 bash 语法、以及引用的变量都有来源）。

## 许可

镜像内二进制来自 Cloudflare, Inc.，以 Apache-2.0 发布，`LICENSE` 原文随镜像分发。
本仓库的构建脚本同样以 Apache-2.0 提供。
