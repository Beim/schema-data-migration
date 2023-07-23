FROM debian:12-slim

WORKDIR /data
USER root
SHELL ["/bin/bash", "-c"]

RUN apt-get update && \
    apt-get install -y git python3.11 python3-pip nodejs npm \
    curl python3-dev default-libmysqlclient-dev build-essential pkg-config python3.11-venv mariadb-client && \
    mkdir /.npm && chown -R 1000:0 "/.npm" && \
    # install skeema \
    mkdir skeema && cd skeema && \
    curl -L https://github.com/skeema/skeema/releases/download/v1.10.1/skeema_1.10.1_linux_amd64.tar.gz | tar xz && \
    mv skeema /usr/local/bin/skeema && \
    cd .. && rm -rf skeema && \
    # install sdm
    git clone -b dev/init https://github.com/Beim/schema-data-migration.git /data/schema-data-migration && \
    cd /data/schema-data-migration && python3 -m venv venv && source venv/bin/activate && \
    pip install . && ln -s /data/schema-data-migration/venv/bin/sdm /usr/local/bin/sdm && \
    # remove unused packages
    apt-get remove -y curl python3-dev default-libmysqlclient-dev build-essential pkg-config && apt-get -y auto-remove && \
    rm -rf /var/lib/apt/lists/* && \
    which sdm

WORKDIR /workspace

CMD ["/bin/bash"]
