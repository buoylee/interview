#!/usr/bin/env bash
set -euo pipefail
cmp -s infra/elasticsearch/products-v3-template.json consistency-verifier/src/main/resources/products-v3-template.json
jq -e '.settings=={"number_of_shards":1,"number_of_replicas":0,"refresh_interval":"1s"} and .mappings.dynamic=="strict" and .mappings._meta=={"schema_version":3,"deletion_mode":"tombstone"} and .mappings.properties=={"product_id":{"type":"long"},"sku":{"type":"keyword"},"name":{"type":"text"},"description":{"type":"text"},"category_id":{"type":"long"},"category_name":{"type":"keyword"},"price_cents":{"type":"long"},"available_quantity":{"type":"integer"},"searchable":{"type":"boolean"},"source_revision":{"type":"long"},"source_updated_at":{"type":"date"}}' infra/elasticsearch/products-v3-template.json >/dev/null
source=consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RestGenerationManager.java
[[ "$(grep -Fc 'response("POST","/_aliases"' "$source")" == 1 ]]
! grep -Eq 'response\("DELETE","/_alias|response\("PUT","/_alias' "$source"
grep -Fq 'INSERT INTO rebuild_run' "$source"
grep -Fq 'alias_swapped=TRUE' "$source"
echo "M5 generation assets contract passed"
