FROM debian:12-slim

WORKDIR /data
USER root
SHELL ["/bin/bash", "-c"]

# libdbd-mysql-perl is the dependency of pt-online-schema-change
RUN set -ex && \
    apt-get update && apt-get install -y --no-install-recommends \
        python3-minimal python3-pip python3-venv \
        libdbd-mysql-perl \
        mariadb-client \
        git wget curl xz-utils && \
    wget percona.com/get/pt-online-schema-change && chmod +x pt-online-schema-change && mv pt-online-schema-change /usr/local/bin/ && \
    apt-get -y auto-remove && rm -rf /var/lib/apt/lists/*

# install node.js from https://github.com/nodejs/docker-node/blob/57d57436d1cb175e5f7c8d501df5893556c886c2/18/bookworm/Dockerfile
ENV NODE_VERSION 18.17.0
ENV ARCH x64
RUN set -ex \
  && curl -fsSLO --compressed "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-$ARCH.tar.xz" \
  && tar -xJf "node-v$NODE_VERSION-linux-$ARCH.tar.xz" -C /usr/local --strip-components=1 --no-same-owner \
  && rm "node-v$NODE_VERSION-linux-$ARCH.tar.xz" \
  && ln -s /usr/local/bin/node /usr/local/bin/nodejs \
  # fix the error: Your cache folder contains root-owned files
  && mkdir /.npm && chown -R 1000:0 "/.npm" \
  && node --version && npm --version

# install skeema
RUN mkdir skeema && cd skeema && \
    curl -L https://github.com/skeema/skeema/releases/download/v1.10.1/skeema_1.10.1_linux_amd64.tar.gz | tar xz && \
    mv skeema /usr/local/bin/skeema && \
    cd .. && rm -rf skeema && skeema --version

RUN mkdir -p /data/schema-data-migration
COPY setup.cfg setup.py pyproject.toml /data/schema-data-migration/
COPY src /data/schema-data-migration/src
COPY .git /data/schema-data-migration/.git

RUN set -ex && \
    apt-get update && apt-get install -y --no-install-recommends python3-dev default-libmysqlclient-dev build-essential pkg-config && \
    cd /data/schema-data-migration && ls -alh && python3 -m venv venv && source venv/bin/activate && \
    pip install . && ln -s /data/schema-data-migration/venv/bin/sdm /usr/local/bin/sdm && \
    pip cache purge && \
    apt-get remove -y python3-dev default-libmysqlclient-dev build-essential pkg-config && apt-get -y auto-remove && \
    rm -rf /var/lib/apt/lists/* && \
    which sdm

WORKDIR /workspace

CMD ["/bin/bash"]
