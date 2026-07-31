# syntax=docker/dockerfile:1.7

# 将已发布镜像重新标记并导出为离线 Docker 归档，不执行任何构建步骤。
ARG SOURCE_IMAGE
FROM ${SOURCE_IMAGE}
