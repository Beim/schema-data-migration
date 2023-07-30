FROM debian:12-slim

WORKDIR /data
USER root
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y git python3.11 python3-pip python3.11-venv nodejs npm percona-toolkit mariadb-client curl && \
    mkdir /.npm && chown -R 1000:0 "/.npm" && \
    apt-get -y auto-remove && rm -rf /var/lib/apt/lists/*

# install skeema
RUN mkdir skeema && cd skeema && \
    curl -L https://github.com/skeema/skeema/releases/download/v1.10.1/skeema_1.10.1_linux_amd64.tar.gz | tar xz && \
    mv skeema /usr/local/bin/skeema && \
    cd .. && rm -rf skeema && which skeema

RUN mkdir -p /data/schema-data-migration
COPY setup.cfg setup.py pyproject.toml /data/schema-data-migration/
COPY src /data/schema-data-migration/src
COPY .git /data/schema-data-migration/.git

RUN apt-get update && apt-get install -y curl python3-dev default-libmysqlclient-dev build-essential pkg-config && \
    cd /data/schema-data-migration && ls -alh && python3 -m venv venv && source venv/bin/activate && \
    pip install . && ln -s /data/schema-data-migration/venv/bin/sdm /usr/local/bin/sdm && \
    apt-get remove -y python3-dev default-libmysqlclient-dev build-essential pkg-config && apt-get -y auto-remove && \
    rm -rf /var/lib/apt/lists/* && \
    which sdm

WORKDIR /workspace

CMD ["/bin/bash"]
