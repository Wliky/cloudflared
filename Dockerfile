# syntax=docker/dockerfile:1
#
# Wliky/cloudflared —— 极限精简的 cloudflared 镜像
#
# 基础层是 scratch，镜像里只有四样东西：
#   /cloudflared                     —— 交叉编译出来的二进制（已 -s -w strip）
#   /etc/ssl/certs/ca-certificates.crt —— Mozilla CA 根证书（与 Cloudflare 边缘建 TLS 必需）
#   /etc/passwd /etc/group           —— 一行 nonroot 条目，让 os/user 能解析 uid 65532
#   /LICENSE                         —— Apache-2.0 原文（我们再分发上游作品，必须随附）
#
# 关于「本文件里没有任何 RUN」——这是刻意的：
#   * 二进制由 CI 在 runner 上交叉编译产出（见 .github/workflows/build.yml），
#     构建上下文里已经放好 out/cloudflared；
#   * 没有 RUN => BuildKit 无需为 arm/v7 等目标平台执行任何指令
#     => 不需要 QEMU 仿真，多架构构建只是几次 COPY，秒级完成。
#
# 构建上下文要求：上下文根目录下直接放好这 5 个文件
#   cloudflared            目标架构的二进制（标准版未打包；UPX 版已打包）
#   ca-certificates.crt    CA 根证书包
#   passwd, group          极简用户数据库
#   LICENSE                上游 LICENSE
#
# CI 用的上下文是 out/plain（标准版）与 out/upx（UPX 版）——
# 两个**互不干扰**的目录，所以 UPX 就地打包不可能污染标准版镜像。
# 本地没有这些文件时无法构建，这是预期行为（先跑 CI 或手工交叉编译）。

FROM scratch

ARG VERSION=""
ARG BUILD_TIME=""
ARG UPX="0"

LABEL org.opencontainers.image.title="cloudflared 极简多架构镜像" \
      org.opencontainers.image.description="从上游源码自编译的极简多架构 cloudflared：scratch 基础层、strip 后二进制，amd64/arm64/armv7/armv6/386 五架构合一，拉取约 9 MB" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_TIME}" \
      org.opencontainers.image.source="https://github.com/Wliky/cloudflared" \
      org.opencontainers.image.url="https://github.com/Wliky/cloudflared" \
      org.opencontainers.image.documentation="https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/" \
      org.opencontainers.image.authors="Wliky (build) / Cloudflare, Inc. (software)" \
      org.opencontainers.image.vendor="Wliky" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.base.name="scratch" \
      com.wliky.cloudflared.upx="${UPX}" \
      com.wliky.cloudflared.upstream="cloudflare/cloudflared"

# 与 Cloudflare 边缘建 TLS 需要根证书
COPY ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# 极简用户数据库（约 90 字节）：scratch 里没有 /etc/passwd，
# 补上之后 os/user 能解析 65532，避免 "unable to determine current user" 类报错。
COPY passwd /etc/passwd
COPY group /etc/group

COPY cloudflared /cloudflared
COPY LICENSE /LICENSE

# HOME 必须显式给：scratch 里没有 passwd 兜底时 os.UserHomeDir() 会失败。
# 本镜像用 token 认证（TUNNEL_TOKEN），不会读写 ~/.cloudflared，所以这个目录不存在也无所谓。
ENV HOME=/home/nonroot

# 非特权 UID，与官方镜像的 nonroot(65532) 对齐，也与 Kubernetes 的 numeric UID 要求一致
USER 65532:65532

# entrypoint 与上游官方镜像/社区镜像保持一致，便于一行替换
ENTRYPOINT ["/cloudflared", "--no-autoupdate"]
CMD ["tunnel", "run"]
