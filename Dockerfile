FROM beim/schema-data-migration:base-0.1.0

RUN mkdir -p /data/schema-data-migration
COPY . /data/schema-data-migration/

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
