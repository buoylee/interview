FROM --platform=linux/amd64 oraclelinux:9-slim

RUN microdnf install -y ca-certificates \
 && curl --fail --location \
      --output /tmp/mysql84-community-release-el9-4.noarch.rpm \
      https://repo.mysql.com/mysql84-community-release-el9-4.noarch.rpm \
 && rpm -Uvh /tmp/mysql84-community-release-el9-4.noarch.rpm \
 && microdnf install -y \
      --enablerepo=mysql-8.4-lts-community \
      --enablerepo=mysql-tools-8.4-lts-community \
      --disablerepo=mysql-9.7-lts-community \
      --disablerepo=mysql-tools-9.7-lts-community \
      mysql-shell-8.4.10-1.el9 \
      mysql-community-client-8.4.10-1.el9 \
 && rm -f /tmp/mysql84-community-release-el9-4.noarch.rpm \
 && microdnf clean all

ENTRYPOINT []
CMD ["mysqlsh"]
