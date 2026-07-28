#!/usr/bin/env bash
set -euo pipefail

grep -Fxq 'canal.instance.filter.regex=product_catalog\\.(product_search_revision|cdc_barrier)' infra/canal/instance.properties
grep -Fxq 'canal.mq.partitionsNum=3' infra/canal/instance.properties
grep -Fxq 'canal.mq.database.hash=false' infra/canal/instance.properties
grep -Fxq 'canal.mq.partitionHash=product_catalog.product_search_revision:product_id,product_catalog.cdc_barrier:partition_token' infra/canal/instance.properties
grep -Fxq 'canal.mq.database.hash = false' infra/canal/canal.properties
grep -Fq 'writeGate.assertOpenForMutation();' product-service/src/main/java/com/interview/mysqlescdc/product/application/ProductMutationService.java
[[ "$(grep -Fc 'writeGate.assertOpenForMutation();' product-service/src/main/java/com/interview/mysqlescdc/product/application/ProductMutationService.java)" == 6 ]]
grep -Fq "CHARACTER_SET_NAME" infra/mysql/verify-rebuild-control-schema.sh
grep -Fq "COLLATION_NAME" infra/mysql/verify-rebuild-control-schema.sh
for field in COLLATION EXPRESSION SUB_PART IS_VISIBLE INDEX_TYPE; do grep -Fq "$field" infra/mysql/verify-rebuild-control-schema.sh; done
grep -Fq 'trap cleanup EXIT INT TERM' tests/contracts/m5-rebuild-schema-drift.sh
grep -Fq 'for round in 1 2' tests/contracts/m5-rebuild-repeat-apply.sh
echo "M5 write-gate/routing contract passed"
