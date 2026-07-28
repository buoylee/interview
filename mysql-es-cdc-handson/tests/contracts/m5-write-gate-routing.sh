#!/usr/bin/env bash
set -euo pipefail

grep -Fxq 'canal.instance.filter.regex=product_catalog\\.(product_search_revision|cdc_barrier)' infra/canal/instance.properties
grep -Fxq 'canal.mq.partitionsNum=3' infra/canal/instance.properties
grep -Fxq 'canal.mq.database.hash=false' infra/canal/instance.properties
grep -Fxq 'canal.mq.partitionHash=product_catalog.product_search_revision:product_id,product_catalog.cdc_barrier:partition_token' infra/canal/instance.properties
grep -Fxq 'canal.mq.database.hash = false' infra/canal/canal.properties
grep -Fq 'writeGate.assertOpenForMutation();' product-service/src/main/java/com/interview/mysqlescdc/product/application/ProductMutationService.java
[[ "$(grep -Fc 'writeGate.assertOpenForMutation();' product-service/src/main/java/com/interview/mysqlescdc/product/application/ProductMutationService.java)" == 6 ]]
echo "M5 write-gate/routing contract passed"
