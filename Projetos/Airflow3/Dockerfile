# Base local já inclui Chromium (build anterior a partir de apache/airflow:3.1.8).
# Node via tarball .tar.gz oficial — sem apt (debian 403 neste ambiente).
# Hermes Agent exige Node >=22.12 para alguns pacotes (electron-rebuild, etc.).
FROM airflow3-with-chromium:3.1.8-base

USER root

ARG NODE_VERSION=22.17.0
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.gz" \
    | tar -xz -C /usr/local --strip-components=1 \
    && node --version \
    && npm --version

ENV HERMES_ROOT=/opt/hermes

USER airflow
