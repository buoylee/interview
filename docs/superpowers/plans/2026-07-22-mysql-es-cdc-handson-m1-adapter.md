# MySQL ES CDC Hands-on M1 Canal Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox - [ ] syntax for tracking.

**Goal:** Establish an evidence-backed black-box baseline for MySQL → canal-server TCP → official Canal ES8 Adapter → Elasticsearch, including restart recovery, source deletion, mapping failure, and Bulk partial-failure behavior.

**Architecture:** M1 adds a second Canal instance in TCP mode so the M0 Kafka path remains untouched. A locally built Adapter image uses the official canal.adapter-1.1.8 release archive and an es8 mapping into products_adapter_v1. Scenario scripts compare MySQL facts, Adapter logs, and Elasticsearch results; they report observed behavior without promoting Adapter behavior into an end-to-end consistency guarantee.

**Tech Stack:** Canal server and Adapter 1.1.8, MySQL 8.4.8, Elasticsearch 8.17.0, Docker Compose v2 profiles/override files, Bash, curl, jq.

## Global Constraints

- Execute only after the M0 completion gate passes.
- Work only in branch codex/mysql-es-cdc-handson and its isolated worktree.
- M1 uses the official Canal 1.1.8 release artifact; do not substitute a third-party Adapter image.
- The official Adapter archive is exactly 291072978 bytes with SHA-256 e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340; download before build and reject any mismatch.
- M1 writes only products_adapter_v1. It must not touch products_v2 or the future search alias.
- Treat the Adapter as a black box. Record its ACK, retry, restart, and partial-failure behavior from evidence.
- Do not reuse M1 observations as a claim of exactly-once or final consistency.
- Normal business deletion remains a soft delete. A hard-delete scenario is explicitly labeled as direct SQL fault injection used only to observe Adapter DELETE handling.
- Every scenario starts from deterministic data and produces machine-readable evidence.
- Do not modify product-service to call the Adapter or Elasticsearch.
- Command context: run build, Compose, script, and Git commands from `mysql-es-cdc-handson/`; file lists in this plan remain repository-worktree-relative.

## Locked File Map

~~~text
mysql-es-cdc-handson/
├── infra/
│   ├── compose.adapter.yaml
│   ├── canal-adapter-server/
│   │   ├── canal.properties
│   │   └── instance.properties
│   └── canal-adapter/
│       ├── Dockerfile
│       ├── entrypoint.sh
│       └── conf/
│           ├── application.yml
│           └── es8/products.yml
├── scenarios/
│   ├── definitions/
│   │   ├── m1-basic.json
│   │   ├── m1-restart.json
│   │   ├── m1-hard-delete.json
│   │   └── m1-bulk-partial.json
│   └── scripts/
│       ├── lib-adapter.sh
│       ├── run-m1-basic.sh
│       ├── run-m1-restart.sh
│       ├── run-m1-hard-delete.sh
│       └── run-m1-bulk-partial.sh
├── tests/contracts/m1-adapter.sh
├── docs/01-canal-boundary.md
└── evidence/m1/.gitkeep
~~~

---

### Task 1: Build the official Canal Adapter image and isolated TCP topology

**Files:**

- Create: mysql-es-cdc-handson/tests/contracts/m1-adapter.sh
- Create: mysql-es-cdc-handson/infra/canal-adapter-server/canal.properties
- Create: mysql-es-cdc-handson/infra/canal-adapter-server/instance.properties
- Create: mysql-es-cdc-handson/infra/canal-adapter/Dockerfile
- Create: mysql-es-cdc-handson/infra/canal-adapter/SHA256SUMS
- Create: mysql-es-cdc-handson/infra/canal-adapter/fetch-release.sh
- Create: mysql-es-cdc-handson/infra/canal-adapter/artifacts/.gitignore
- Create: mysql-es-cdc-handson/infra/canal-adapter/entrypoint.sh
- Create: mysql-es-cdc-handson/infra/canal-adapter/conf/application.yml
- Create: mysql-es-cdc-handson/infra/compose.adapter.yaml

**Interfaces:**

- Consumes: product_catalog.products changes through destination products_adapter.
- Produces: canal-adapter-server:11111 in the Compose network and Canal Adapter readiness at host port 8084.

- [ ] **Step 1: Write the failing Adapter topology contract**

Create tests/contracts/m1-adapter.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

docker compose \
  -f infra/compose.yaml \
  -f infra/compose.adapter.yaml \
  config --quiet

grep -Fq "FROM canal/canal-server:v1.1.8" infra/canal-adapter/Dockerfile
grep -Fq "canal.adapter-1.1.8.tar.gz" infra/canal-adapter/Dockerfile
grep -Fq "e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340" infra/canal-adapter/SHA256SUMS
grep -Fq "canal.serverMode = tcp" infra/canal-adapter-server/canal.properties
grep -Fq "canal.instance.mysql.slaveId=1235" \
  infra/canal-adapter-server/instance.properties
grep -Fq "canal.instance.filter.regex=product_catalog\\\\.products" \
  infra/canal-adapter-server/instance.properties
grep -Fq "name: es8" infra/canal-adapter/conf/application.yml
~~~

- [ ] **Step 2: Run the contract and verify the red state**

Run:

~~~bash
bash tests/contracts/m1-adapter.sh
~~~

Expected: FAIL because the Adapter topology files do not exist.

- [ ] **Step 3: Configure a TCP-only Canal destination**

Create infra/canal-adapter-server/canal.properties:

~~~properties
canal.id = 2
canal.ip =
canal.port = 11111
canal.metrics.pull.port = 11112
canal.destinations = products_adapter
canal.auto.scan = false
canal.serverMode = tcp
canal.file.data.dir = ../conf
canal.file.flush.period = 1000
canal.instance.memory.buffer.size = 16384
canal.instance.memory.buffer.memunit = 1024
canal.instance.memory.batch.mode = MEMSIZE
canal.instance.memory.rawEntry = true
canal.instance.detecting.enable = false
canal.instance.transaction.size = 1024
canal.instance.binlog.format = ROW
canal.instance.binlog.image = FULL
canal.instance.tsdb.enable = true
~~~

Create infra/canal-adapter-server/instance.properties:

~~~properties
canal.instance.mysql.slaveId=1235
canal.instance.gtidon=true
canal.instance.master.address=mysql:3306
canal.instance.master.journal.name=
canal.instance.master.position=
canal.instance.master.timestamp=
canal.instance.master.gtid=
canal.instance.dbUsername=canal
canal.instance.dbPassword=canalpass
canal.instance.connectionCharset=UTF-8
canal.instance.enableDruid=false
canal.instance.filter.regex=product_catalog\\.products
canal.instance.filter.black.regex=
canal.instance.tsdb.enable=true
~~~

- [ ] **Step 4: Build Adapter 1.1.8 from the official release asset**

Create infra/canal-adapter/SHA256SUMS:

~~~text
e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340  canal.adapter-1.1.8.tar.gz
~~~

Create infra/canal-adapter/artifacts/.gitignore:

~~~gitignore
*.tar.gz
!.gitignore
~~~

Create infra/canal-adapter/fetch-release.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

base_dir="$(cd "$(dirname "$0")" && pwd)"
artifact_dir="$base_dir/artifacts"
archive="$artifact_dir/canal.adapter-1.1.8.tar.gz"
partial="$archive.partial"
mkdir -p "$artifact_dir"

verify_archive() {
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "$artifact_dir" && sha256sum -c ../SHA256SUMS)
  else
    (cd "$artifact_dir" && shasum -a 256 -c ../SHA256SUMS)
  fi
}

if test -f "$archive" && verify_archive; then
  exit 0
fi

rm -f "$partial"
curl -fL https://github.com/alibaba/canal/releases/download/canal-1.1.8/canal.adapter-1.1.8.tar.gz -o "$partial"
test "$(stat -f '%z' "$partial" 2>/dev/null || stat -c '%s' "$partial")" = 291072978
mv "$partial" "$archive"
verify_archive
~~~

Run `bash infra/canal-adapter/fetch-release.sh` before every Adapter image build. The archive stays ignored; the checksum and fetch script are committed.

Create infra/canal-adapter/Dockerfile:

~~~dockerfile
FROM canal/canal-server:v1.1.8

USER root
COPY SHA256SUMS /tmp/SHA256SUMS
COPY artifacts/canal.adapter-1.1.8.tar.gz /tmp/canal.adapter-1.1.8.tar.gz
RUN cd /tmp \
    && sha256sum -c SHA256SUMS \
    && mkdir -p /opt/canal-adapter \
    && tar -xzf /tmp/canal.adapter-1.1.8.tar.gz -C /opt/canal-adapter \
    && rm /tmp/canal.adapter-1.1.8.tar.gz /tmp/SHA256SUMS

COPY entrypoint.sh /opt/canal-adapter/entrypoint.sh
COPY conf/application.yml /opt/canal-adapter/conf/application.yml
COPY conf/es8/products.yml /opt/canal-adapter/conf/es8/products.yml

RUN chmod +x /opt/canal-adapter/entrypoint.sh \
    && chown -R admin:admin /opt/canal-adapter

USER admin
WORKDIR /opt/canal-adapter
EXPOSE 8081
ENTRYPOINT ["/opt/canal-adapter/entrypoint.sh"]
~~~

Create infra/canal-adapter/entrypoint.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

cd /opt/canal-adapter
./bin/startup.sh

for attempt in $(seq 1 60); do
  if test -f logs/adapter/adapter.log; then
    exec tail -n +1 -F logs/adapter/adapter.log
  fi
  sleep 1
done

echo "Canal Adapter log did not appear" >&2
exit 1
~~~

- [ ] **Step 5: Configure Adapter TCP input and ES8 output**

Create infra/canal-adapter/conf/application.yml:

~~~yaml
server:
  port: 8081

spring:
  jackson:
    date-format: yyyy-MM-dd HH:mm:ss
    time-zone: UTC
    default-property-inclusion: non_null

management:
  endpoints:
    web:
      exposure:
        include: health,info

canal.conf:
  mode: tcp
  flatMessage: true
  syncBatchSize: 1000
  retries: 0
  timeout:
  consumerProperties:
    canal.tcp.server.host: canal-adapter-server:11111
    canal.tcp.zookeeper.hosts:
    canal.tcp.batch.size: 500
    canal.tcp.username:
    canal.tcp.password:
  srcDataSources:
    defaultDS:
      url: jdbc:mysql://mysql:3306/product_catalog?useUnicode=true&serverTimezone=UTC
      username: product
      password: productpass
  canalAdapters:
    - instance: products_adapter
      groups:
        - groupId: g1
          outerAdapters:
            - name: es8
              hosts: elasticsearch:9200
              properties:
                mode: rest
                security.auth:
                cluster.name: docker-cluster
~~~

- [ ] **Step 6: Add the isolated Compose override**

Create infra/compose.adapter.yaml:

~~~yaml
services:
  canal-adapter-server:
    image: canal/canal-server:v1.1.8
    depends_on:
      mysql:
        condition: service_healthy
    ports: ["11121:11111", "11122:11112"]
    volumes:
      - ./canal-adapter-server/canal.properties:/home/admin/canal-server/conf/canal.properties:ro
      - ./canal-adapter-server/instance.properties:/home/admin/canal-server/conf/products_adapter/instance.properties:ro

  canal-adapter:
    build:
      context: ./canal-adapter
    depends_on:
      canal-adapter-server:
        condition: service_started
      elasticsearch:
        condition: service_healthy
    ports: ["8084:8081"]
~~~

- [ ] **Step 7: Validate and start the Adapter topology**

Run:

~~~bash
chmod +x infra/canal-adapter/entrypoint.sh tests/contracts/m1-adapter.sh
bash tests/contracts/m1-adapter.sh
bash infra/canal-adapter/fetch-release.sh
docker compose \
  -f infra/compose.yaml \
  -f infra/compose.adapter.yaml \
  up -d --build mysql elasticsearch canal-adapter-server canal-adapter
curl -fsS http://localhost:8084/actuator/health
~~~

Expected: configuration validates, Adapter health is UP, and logs show one loaded es8 outer adapter for destination products_adapter.

- [ ] **Step 8: Commit the Adapter topology**

~~~bash
git add infra tests/contracts/m1-adapter.sh
git commit -m "feat(cdc-lab): add Canal ES8 Adapter baseline"
~~~

---

### Task 2: Define the Adapter mapping and deterministic baseline experiment

**Files:**

- Create: mysql-es-cdc-handson/infra/canal-adapter/conf/es8/products.yml
- Create: mysql-es-cdc-handson/infra/elasticsearch/adapter-index.json
- Create: mysql-es-cdc-handson/scenarios/definitions/m1-basic.json
- Create: mysql-es-cdc-handson/scenarios/scripts/lib-adapter.sh
- Create: mysql-es-cdc-handson/scenarios/scripts/run-m1-basic.sh
- Create: mysql-es-cdc-handson/evidence/m1/.gitkeep

**Interfaces:**

- Consumes: products INSERT and UPDATE row events.
- Produces: products_adapter_v1 documents containing only id, sku, name, description, category_id, price_cents, status, and updated_at.

- [ ] **Step 1: Write the failing mapping assertion**

Append to tests/contracts/m1-adapter.sh:

~~~bash
grep -Fq "_index: products_adapter_v1" \
  infra/canal-adapter/conf/es8/products.yml
grep -Fq "FROM products p" \
  infra/canal-adapter/conf/es8/products.yml
~~~

Run the contract.

Expected: FAIL because products.yml does not exist.

- [ ] **Step 2: Add the simple single-table mapping**

Create infra/canal-adapter/conf/es8/products.yml:

~~~yaml
dataSourceKey: defaultDS
destination: products_adapter
groupId: g1
esMapping:
  _index: products_adapter_v1
  _id: _id
  upsert: true
  sql: >
    SELECT
      p.id AS _id,
      p.id AS product_id,
      p.sku,
      p.name,
      p.description,
      p.category_id,
      p.price_cents,
      p.status,
      DATE_FORMAT(p.updated_at, '%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at
    FROM products p
  etlCondition: WHERE p.id > {}
  commitBatch: 1000
~~~

This mapping intentionally excludes category_name, inventory, searchable, and source_revision. M1 is therefore not the final search projection.

Create `infra/elasticsearch/adapter-index.json`:

~~~json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "1s"
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "product_id": {"type": "long"},
      "sku": {"type": "keyword"},
      "name": {"type": "text"},
      "description": {"type": "text"},
      "category_id": {"type": "long"},
      "price_cents": {"type": "long"},
      "status": {"type": "keyword"},
      "updated_at": {"type": "date"}
    }
  }
}
~~~

- [ ] **Step 3: Define the baseline scenario input**

Create scenarios/definitions/m1-basic.json:

~~~json
{
  "scenario_id": "m1-basic",
  "purpose": "Observe Adapter insert and update behavior without failures",
  "source_products": [
    {
      "id": 1101,
      "sku": "M1-1101",
      "name": "Adapter Keyboard",
      "description": "initial",
      "category_id": 10,
      "price_cents": 100,
      "status": "ACTIVE"
    }
  ],
  "mutations": [
    {
      "operation": "change_price",
      "product_id": 1101,
      "price_cents": 120
    }
  ]
}
~~~

- [ ] **Step 4: Add shared black-box helpers**

Create scenarios/scripts/lib-adapter.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

compose_adapter() {
  docker compose -f infra/compose.yaml -f infra/compose.adapter.yaml "$@"
}

wait_for_es_document() {
  local id="$1"
  local expected_price="$2"
  local deadline="$3"
  local start
  start="$(date +%s)"
  while true; do
    if curl -fsS "http://localhost:9200/products_adapter_v1/_doc/$id" \
      | jq -e --argjson price "$expected_price" \
        '.found == true and ._source.price_cents == $price' >/dev/null
    then
      return 0
    fi
    if test "$(( $(date +%s) - start ))" -ge "$deadline"; then
      return 1
    fi
    sleep 1
  done
}

snapshot_product() {
  local id="$1"
  compose_adapter exec -T mysql \
    mysql -uproduct -pproductpass product_catalog --batch --raw --skip-column-names \
    -e "SELECT JSON_OBJECT(
          'id', id,
          'sku', sku,
          'name', name,
          'description', description,
          'category_id', category_id,
          'price_cents', price_cents,
          'status', status
        ) FROM products WHERE id = $id"
}
~~~

- [ ] **Step 5: Write the baseline runner**

Create scenarios/scripts/run-m1-basic.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-adapter.sh

scenario="m1-basic"
out="evidence/m1/$scenario"
rm -rf "$out"
mkdir -p "$out"
cp "scenarios/definitions/$scenario.json" "$out/input-commands.json"

curl -fsS -X DELETE http://localhost:9200/products_adapter_v1 >/dev/null || true
curl -fsS -X PUT http://localhost:9200/products_adapter_v1 \
  -H 'Content-Type: application/json' \
  --data-binary @infra/elasticsearch/adapter-index.json \
  > "$out/index-create.json"

curl -fsS -X POST http://localhost:8081/api/products \
  -H 'Content-Type: application/json' \
  -d '{"id":1101,"sku":"M1-1101","name":"Adapter Keyboard","description":"initial","categoryId":10,"priceCents":100}' \
  > "$out/create-response.json"

wait_for_es_document 1101 100 60

curl -fsS -X PUT http://localhost:8081/api/products/1101/price \
  -H 'Content-Type: application/json' \
  -d '{"priceCents":120}' \
  > "$out/update-response.json"

wait_for_es_document 1101 120 60
snapshot_product 1101 | jq . > "$out/mysql-snapshot.json"
curl -fsS http://localhost:9200/products_adapter_v1/_doc/1101 \
  | jq . > "$out/es-snapshot.json"
compose_adapter logs --no-color canal-adapter > "$out/adapter.log"

jq -n \
  --arg scenario "$scenario" \
  --arg result "OBSERVED_INSERT_UPDATE_RECOVERY" \
  '{scenario_id:$scenario,result:$result,final_consistency_claim:false}' \
  > "$out/result.json"
~~~

- [ ] **Step 6: Run and verify the baseline**

Run:

~~~bash
chmod +x scenarios/scripts/lib-adapter.sh scenarios/scripts/run-m1-basic.sh
bash scenarios/scripts/run-m1-basic.sh
jq -e '.result == "OBSERVED_INSERT_UPDATE_RECOVERY"' \
  evidence/m1/m1-basic/result.json
~~~

Expected: ES document 1101 reaches price_cents 120; evidence contains source, target, Adapter log, and an explicit final_consistency_claim=false.

- [ ] **Step 7: Commit the baseline mapping and scenario**

~~~bash
git add infra scenarios evidence/m1/.gitkeep
git commit -m "test(cdc-lab): record Adapter insert and update behavior"
~~~

---

### Task 3: Measure restart and hard-delete behavior

**Files:**

- Create: mysql-es-cdc-handson/scenarios/definitions/m1-restart.json
- Create: mysql-es-cdc-handson/scenarios/definitions/m1-hard-delete.json
- Create: mysql-es-cdc-handson/scenarios/scripts/run-m1-restart.sh
- Create: mysql-es-cdc-handson/scenarios/scripts/run-m1-hard-delete.sh

**Interfaces:**

- Consumes: Adapter process restart and a direct SQL hard-delete transaction.
- Produces: evidence showing whether the Adapter resumes from its position and whether a products DELETE removes the target ES document.

- [ ] **Step 1: Define restart and hard-delete inputs**

Create m1-restart.json:

~~~json
{
  "scenario_id": "m1-restart",
  "fault": "stop canal-adapter while source revisions advance",
  "recovery": "restart the same container without deleting its state",
  "expected_observation": "document reaches the latest source value or evidence records the gap"
}
~~~

Create m1-hard-delete.json:

~~~json
{
  "scenario_id": "m1-hard-delete",
  "fault": "delete revision, inventory, and product rows in one direct SQL transaction",
  "normal_business_path": false,
  "expected_observation": "Adapter DELETE behavior is measured, not assumed"
}
~~~

- [ ] **Step 2: Implement the restart runner**

run-m1-restart.sh must perform these exact state transitions:

1. Reset products_adapter_v1 and create product 1201.
2. Wait until ES contains price 100.
3. Stop only canal-adapter.
4. Change source price to 200 and inventory once while Adapter is down.
5. Start the same canal-adapter container.
6. Poll ES for price 200 for at most 60 seconds.
7. Record start/stop times, MySQL snapshot, ES snapshot, Adapter logs, and either OBSERVED_RESTART_RECOVERY or OBSERVED_RESTART_GAP.

The result writer must not force a green result:

~~~bash
if wait_for_es_document 1201 200 60; then
  result="OBSERVED_RESTART_RECOVERY"
else
  result="OBSERVED_RESTART_GAP"
fi
jq -n --arg scenario "m1-restart" --arg result "$result" \
  '{scenario_id:$scenario,result:$result,final_consistency_claim:false}' \
  > "$out/result.json"
~~~

- [ ] **Step 3: Implement the hard-delete runner**

run-m1-hard-delete.sh must:

1. Create product 1301 through product-service.
2. Wait until products_adapter_v1 contains it.
3. Execute this direct SQL transaction:

~~~sql
START TRANSACTION;
DELETE FROM product_search_revision WHERE product_id = 1301;
DELETE FROM inventory WHERE product_id = 1301;
DELETE FROM products WHERE id = 1301;
COMMIT;
~~~

4. Poll GET products_adapter_v1/_doc/1301 until found=false or 60 seconds elapse.
5. Emit OBSERVED_DELETE_PROPAGATION or OBSERVED_DELETE_GAP without changing expectations after the run.

- [ ] **Step 4: Execute each scenario twice**

Run:

~~~bash
bash scenarios/scripts/run-m1-restart.sh
cp -R evidence/m1/m1-restart evidence/m1/m1-restart-first
bash scenarios/scripts/run-m1-restart.sh

bash scenarios/scripts/run-m1-hard-delete.sh
cp -R evidence/m1/m1-hard-delete evidence/m1/m1-hard-delete-first
bash scenarios/scripts/run-m1-hard-delete.sh
~~~

Expected: both runs produce valid result.json and complete evidence. The observed result may be recovery or gap; documentation must reflect the evidence.

- [ ] **Step 5: Commit restart and delete evidence contracts**

~~~bash
git add scenarios
git commit -m "test(cdc-lab): measure Adapter restart and delete semantics"
~~~

---

### Task 4: Force a Bulk partial failure and document the Canal boundary

**Files:**

- Create: mysql-es-cdc-handson/infra/elasticsearch/adapter-index-partial-failure.json
- Create: mysql-es-cdc-handson/scenarios/definitions/m1-bulk-partial.json
- Create: mysql-es-cdc-handson/scenarios/scripts/run-m1-bulk-partial.sh
- Create: mysql-es-cdc-handson/scenarios/scripts/render-m1-boundary.sh
- Create: mysql-es-cdc-handson/docs/01-canal-boundary.md
- Modify: mysql-es-cdc-handson/Makefile
- Modify: mysql-es-cdc-handson/README.md

**Interfaces:**

- Consumes: one valid and one invalid price_cents value in the same Adapter batch against an intentionally narrow byte mapping.
- Produces: evidence of per-document target state, Adapter logs, and the actual recovery requirement after mapping repair.

- [ ] **Step 1: Define the incompatible index**

Create adapter-index-partial-failure.json:

~~~json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "1s"
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "product_id": {"type": "long"},
      "sku": {"type": "keyword"},
      "name": {"type": "keyword"},
      "description": {"type": "text"},
      "category_id": {"type": "long"},
      "price_cents": {"type": "byte"},
      "status": {"type": "keyword"},
      "updated_at": {"type": "date"}
    }
  }
}
~~~

Create m1-bulk-partial.json:

~~~json
{
  "scenario_id": "m1-bulk-partial",
  "target_mapping": "price_cents is byte",
  "same_source_transaction": [
    {"product_id": 1401, "price_cents": 100, "expected_mapping": "valid"},
    {"product_id": 1402, "price_cents": 1000, "expected_mapping": "invalid"}
  ],
  "later_source_transaction": {
    "product_id": 1403,
    "price_cents": 101,
    "purpose": "prove whether Adapter advances beyond the failed batch"
  },
  "question": "Does Adapter advance, retry, partially apply, or require ETL after one item fails?"
}
~~~

- [ ] **Step 2: Implement the deterministic partial-failure runner**

run-m1-bulk-partial.sh must:

1. Stop Adapter.
2. Recreate products_adapter_v1 using adapter-index-partial-failure.json.
3. Insert products 1401 and 1402 in one direct MySQL transaction, including inventory and revision rows.
4. Start Adapter and wait until logs contain either a Bulk error or both IDs have terminal target states.
5. Capture GET results for both IDs separately.
6. Insert valid product 1403 in a later source transaction and poll for it for at most 30 seconds. Its presence proves Adapter advanced past the failed batch; its absence is recorded as `false`, not guessed.
7. Recreate the normal long mapping.
8. Restart Adapter without manually moving its cursor and observe whether 1402 appears.
9. If it does not appear, invoke the Adapter ETL endpoint for the mapping and record that explicit repair action.
10. Derive every result field from the captured GET responses:

~~~bash
valid_item_applied=$(jq -r '.found == true' "$out/1401-before-fix.json")
invalid_item_applied_before_fix=$(jq -r '.found == true' "$out/1402-before-fix.json")
later_batch_applied_before_fix=$(jq -r '.found == true' "$out/1403-before-fix.json")
invalid_item_retried_after_fix=$(jq -r '.found == true' "$out/1402-after-restart.json")
if test "$invalid_item_retried_after_fix" = "true"; then
  etl_required=false
else
  etl_required=true
fi

jq -n \
  --argjson valid "$valid_item_applied" \
  --argjson invalidBefore "$invalid_item_applied_before_fix" \
  --argjson later "$later_batch_applied_before_fix" \
  --argjson retried "$invalid_item_retried_after_fix" \
  --argjson etl "$etl_required" \
  '{
    scenario_id:"m1-bulk-partial",
    valid_item_applied:$valid,
    invalid_item_applied_before_mapping_fix:$invalidBefore,
    later_batch_applied_before_mapping_fix:$later,
    invalid_item_retried_after_mapping_fix:$retried,
    etl_required:$etl,
    final_consistency_claim:false
  }' > "$out/result.json"
~~~

The resulting file has only concrete booleans:

~~~json
{
  "scenario_id": "m1-bulk-partial",
  "valid_item_applied": false,
  "invalid_item_applied_before_mapping_fix": false,
  "later_batch_applied_before_mapping_fix": false,
  "invalid_item_retried_after_mapping_fix": false,
  "etl_required": false,
  "final_consistency_claim": false
}
~~~

- [ ] **Step 3: Run the partial-failure scenario and validate evidence completeness**

Run:

~~~bash
bash scenarios/scripts/run-m1-bulk-partial.sh
jq -e '
  has("valid_item_applied")
  and has("invalid_item_applied_before_mapping_fix")
  and has("later_batch_applied_before_mapping_fix")
  and has("invalid_item_retried_after_mapping_fix")
  and has("etl_required")
  and (.valid_item_applied | type) == "boolean"
  and (.later_batch_applied_before_mapping_fix | type) == "boolean"
  and .final_consistency_claim == false
' evidence/m1/m1-bulk-partial/result.json
~~~

Expected: the validation passes regardless of which black-box behavior was observed.

- [ ] **Step 4: Write the boundary document from evidence**

Create `render-m1-boundary.sh` so observed values are never hand-edited into claims:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

basic=$(jq -r '.result' evidence/m1/m1-basic/result.json)
restart=$(jq -r '.result' evidence/m1/m1-restart/result.json)
hard_delete=$(jq -r '.result' evidence/m1/m1-hard-delete/result.json)
valid=$(jq -r '.valid_item_applied' evidence/m1/m1-bulk-partial/result.json)
later=$(jq -r '.later_batch_applied_before_mapping_fix' evidence/m1/m1-bulk-partial/result.json)
retried=$(jq -r '.invalid_item_retried_after_mapping_fix' evidence/m1/m1-bulk-partial/result.json)
etl=$(jq -r '.etl_required' evidence/m1/m1-bulk-partial/result.json)

{
  printf '%s\n' '# Canal and Adapter evidence boundary'
  printf '%s\n' '' '## What Canal provides'
  printf '%s\n' 'Canal captures and parses committed MySQL binlog changes and delivers row-change data through its TCP or MQ output. It is a CDC/incremental-subscription component, not an end-to-end consistency solution.'
  printf '%s\n' '' '## Observed Adapter behavior'
  printf -- '- `m1-basic.result`: `%s` ([evidence](../evidence/m1/m1-basic/result.json))\n' "$basic"
  printf -- '- `m1-restart.result`: `%s` ([evidence](../evidence/m1/m1-restart/result.json))\n' "$restart"
  printf -- '- `m1-hard-delete.result`: `%s` ([evidence](../evidence/m1/m1-hard-delete/result.json))\n' "$hard_delete"
  printf '%s\n' '' '## Bulk partial-failure observation'
  printf -- '- valid item applied: `%s`\n' "$valid"
  printf -- '- later batch applied before mapping fix: `%s`\n' "$later"
  printf -- '- invalid item retried after mapping fix: `%s`\n' "$retried"
  printf -- '- explicit ETL required: `%s`\n' "$etl"
  printf '%s\n' 'Evidence: [m1-bulk-partial/result.json](../evidence/m1/m1-bulk-partial/result.json).'
  printf '%s\n' '' '## Missing end-to-end capabilities'
  printf '%s\n' 'M1 does not provide the final multi-table projection, revision fencing, per-Bulk-item settlement contract, durable DLQ, independent reconciliation, log-gap classification, or full rebuild/cutover workflow.'
  printf '%s\n' '' '## Verdict'
  printf '%s\n' 'M1 narrows the uncertainty around the official Adapter path under the recorded versions. None of its result files claims MySQL-to-Elasticsearch final consistency.'
} > docs/01-canal-boundary.md
~~~

Run the renderer after all four scenarios. Every Adapter claim then names a scenario and exact result field.

- [ ] **Step 5: Add M1 commands**

Add these targets to Makefile:

~~~make
.PHONY: up-adapter scenario-m1 verify-m1

up-adapter: package
	bash infra/canal-adapter/fetch-release.sh
	$(COMPOSE) -f infra/compose.adapter.yaml up -d --build

scenario-m1: up-adapter
	bash scenarios/scripts/run-m1-basic.sh
	bash scenarios/scripts/run-m1-restart.sh
	bash scenarios/scripts/run-m1-hard-delete.sh
	bash scenarios/scripts/run-m1-bulk-partial.sh

verify-m1:
	bash tests/contracts/m1-adapter.sh
	jq -e '.final_consistency_claim == false' evidence/m1/m1-basic/result.json
	jq -e '.final_consistency_claim == false' evidence/m1/m1-bulk-partial/result.json
~~~

Append this exact README paragraph:

~~~markdown
## M1: official Adapter comparison

The [Canal and Adapter evidence boundary](docs/01-canal-boundary.md) records black-box behavior for the official 1.1.8 Adapter. `products_adapter_v1` is a disposable comparison index; it is never the serving index and is not evidence of the final consistency contract.
~~~

- [ ] **Step 6: Run the M1 completion gate**

Run:

~~~bash
make verify
make scenario-m1
make verify-m1
git diff --check
~~~

Expected: all scenario evidence is structurally complete, and no M1 result claims final consistency.

- [ ] **Step 7: Commit M1**

~~~bash
git add .
git commit -m "docs(cdc-lab): establish Canal Adapter evidence boundary"
~~~

## M1 Completion Gate

Do not start M2 until:

- the Adapter image demonstrably came from canal.adapter-1.1.8;
- products_adapter_v1 contains only the documented single-table projection;
- basic, restart, hard-delete, and Bulk partial-failure scenarios each have result.json;
- every black-box claim in docs/01-canal-boundary.md points to observed evidence;
- the document explicitly refuses an end-to-end final-consistency claim;
- the M0 Kafka path still passes after the Adapter profile is stopped;
- git status is clean.
