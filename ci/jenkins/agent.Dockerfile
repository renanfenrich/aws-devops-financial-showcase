FROM jenkins/inbound-agent:jdk25@sha256:9f243ac38c833d2955fa8e36220329d55e232d46667769c02376cd246e3250a3
USER root
RUN apt-get update && apt-get install -y --no-install-recommends make python3 git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY scripts/bootstrap.py /opt/showcase/scripts/bootstrap.py
COPY toolchain.lock.json /opt/showcase/toolchain.lock.json
RUN python3 /opt/showcase/scripts/bootstrap.py --only uv terraform terragrunt tflint helm actionlint promtool
ENV PATH="/opt/showcase/.tools/bin:${PATH}" UV_PYTHON_INSTALL_DIR="/opt/python" UV_PYTHON="3.14.10"
RUN uv python install 3.14.10 && chmod -R a+rX /opt/python
USER jenkins
