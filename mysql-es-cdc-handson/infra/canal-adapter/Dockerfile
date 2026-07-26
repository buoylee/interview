FROM canal/canal-server:v1.1.8

USER root
COPY SHA256SUMS /tmp/SHA256SUMS
COPY artifacts/canal.adapter-1.1.8.tar.gz /tmp/canal.adapter-1.1.8.tar.gz
RUN cd /tmp \
    && test "$(wc -c < canal.adapter-1.1.8.tar.gz)" = 291072978 \
    && sha256sum -c SHA256SUMS \
    && mkdir -p /opt/canal-adapter \
    && tar -xzf canal.adapter-1.1.8.tar.gz -C /opt/canal-adapter \
    && rm canal.adapter-1.1.8.tar.gz SHA256SUMS

COPY entrypoint.sh /opt/canal-adapter/entrypoint.sh
COPY conf/ /opt/canal-adapter/conf/

RUN chmod +x /opt/canal-adapter/entrypoint.sh \
    && chown -R admin:admin /opt/canal-adapter

USER admin
WORKDIR /opt/canal-adapter
EXPOSE 8081
ENTRYPOINT ["/opt/canal-adapter/entrypoint.sh"]
