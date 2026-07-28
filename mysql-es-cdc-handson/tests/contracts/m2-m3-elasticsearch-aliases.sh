#!/usr/bin/env bash
set -euo pipefail

bash -n infra/elasticsearch/bootstrap-products-v2.sh
bash -n scenarios/scripts/verify-products-v2-versioning.sh

grep -Fq 'version_type' search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/RestElasticsearchGateway.java
grep -Fq 'external' search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/RestElasticsearchGateway.java
grep -Fq 'require_alias=true' search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/RestElasticsearchGateway.java
grep -Fq 'keys == ["products_v2"]' infra/elasticsearch/bootstrap-products-v2.sh
grep -Fq 'products_search/_search' scenarios/scripts/verify-products-v2-versioning.sh

echo "M2-M3 Elasticsearch alias contracts passed"
