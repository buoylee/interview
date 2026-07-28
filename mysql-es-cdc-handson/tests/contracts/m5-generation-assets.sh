#!/usr/bin/env bash
set -euo pipefail
cmp -s infra/elasticsearch/products-v3-template.json consistency-verifier/src/main/resources/products-v3-template.json
jq -e '.settings=={"number_of_shards":1,"number_of_replicas":0,"refresh_interval":"1s"} and .mappings.dynamic=="strict" and .mappings._meta=={"schema_version":3,"deletion_mode":"tombstone"} and (.mappings.properties|length)==11' infra/elasticsearch/products-v3-template.json >/dev/null
source=consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RestGenerationManager.java
[[ "$(grep -Fc 'response("POST","/_aliases"' "$source")" == 1 ]]
! grep -Eq 'response\("DELETE","/_alias|response\("PUT","/_alias' "$source"
grep -Fq 'INSERT INTO rebuild_run' "$source"
grep -Fq 'alias_swapped=TRUE' "$source"
echo "M5 generation assets contract passed"
