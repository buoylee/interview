SHELL := /bin/bash
COMPOSE := docker compose -f infra/compose.yaml
COMPOSE_ADAPTER := $(COMPOSE) -f infra/compose.adapter.yaml

.PHONY: assert-java-21 package up up-adapter down reset scenario evidence verify verify-fast smoke-m0 scenario-m1 verify-m1 gate-m1 bootstrap-products-v2 bootstrap-index verify-products-v2 scenario-m3-after-es scenario-m3-after-dlq scenario-m3 verify-m3 gate-m2-m3 reconcile scenario-m4 verify-m4 rebuild scenario-m5 verify-m5 formal-final-m5

assert-java-21:
	@java -version 2>&1 | head -n 1 | grep -Eq 'version "21([.]|\")' || { \
		echo "Java 21 is required. Set JAVA_HOME to a Temurin 21 installation before running make." >&2; \
		exit 1; \
	}

package: assert-java-21
	./mvnw -q -DskipTests package

up: package
	$(COMPOSE) up -d --build

up-adapter: package
	bash infra/canal-adapter/fetch-release.sh
	$(COMPOSE_ADAPTER) up -d --build mysql elasticsearch product-service canal-adapter-server canal-adapter

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) --profile m0-tools down --volumes --remove-orphans

scenario:
	test -n "$(SCENARIO)"
	bash scenarios/scripts/run-scenario.sh "$(SCENARIO)"

evidence:
	bash tests/end-to-end/m6-fault-matrix.sh

verify-fast:
	./mvnw -q test
	for test_script in tests/contracts/*.sh; do bash "$$test_script"; done

verify: verify-fast
	$(MAKE) reset
	$(MAKE) up
	bash tests/end-to-end/m0-smoke.sh
	bash tests/end-to-end/m4-reconciliation.sh
	bash tests/end-to-end/m5-rebuild.sh

smoke-m0: up
	bash scenarios/scripts/smoke-m0.sh

scenario-m1: up-adapter
	bash scenarios/scripts/run-m1-basic.sh
	bash scenarios/scripts/run-m1-restart.sh
	bash scenarios/scripts/run-m1-hard-delete.sh
	bash scenarios/scripts/run-m1-bulk-partial.sh
	bash scenarios/scripts/render-m1-boundary.sh

verify-m1:
	bash tests/contracts/m1-adapter.sh
	bash tests/contracts/m1-mapping-proof.sh
	bash tests/contracts/m1-evidence.sh
	bash tests/contracts/m1-log-window.sh
	bash tests/contracts/m1-process-identity.sh
	bash tests/contracts/m1-restart-evidence.sh
	bash tests/contracts/m1-hard-delete-evidence.sh
	bash tests/contracts/m1-bulk-partial-evidence.sh
	bash scenarios/scripts/assert-m1-evidence.sh evidence/m1/m1-basic
	bash scenarios/scripts/assert-m1-restart-evidence.sh evidence/m1/m1-restart
	bash scenarios/scripts/assert-m1-hard-delete-evidence.sh evidence/m1/m1-hard-delete
	bash scenarios/scripts/assert-m1-bulk-partial-evidence.sh evidence/m1/m1-bulk-partial
	bash scenarios/scripts/assert-m1-boundary-doc.sh docs/01-canal-boundary.md
	bash tests/contracts/m1-boundary-doc.sh

gate-m1:
	$(MAKE) verify-m1
	$(COMPOSE_ADAPTER) stop canal-adapter canal-adapter-server
	$(COMPOSE_ADAPTER) rm -f canal-adapter canal-adapter-server
	@adapter_ids="$$($(COMPOSE_ADAPTER) ps -a -q canal-adapter canal-adapter-server)"; \
	if test -n "$$adapter_ids"; then \
		echo "Adapter comparison containers still exist: $$adapter_ids" >&2; \
		exit 1; \
	fi
	$(MAKE) reset
	$(MAKE) smoke-m0
	git diff --exit-code -- docs/01-canal-boundary.md
	@tracked_status="$$(git status --porcelain --untracked-files=no)"; \
	if test -n "$$tracked_status"; then \
		echo "Tracked worktree is not clean after M1 gate:" >&2; \
		echo "$$tracked_status" >&2; \
		exit 1; \
	fi

bootstrap-products-v2:
	bash infra/elasticsearch/bootstrap-products-v2.sh

bootstrap-index: bootstrap-products-v2

verify-products-v2:
	bash tests/contracts/m2-m3-elasticsearch-aliases.sh
	bash tests/contracts/m2-m3-bootstrap-fail-closed.sh
	bash scenarios/scripts/verify-products-v2-versioning.sh

scenario-m3-after-es:
	bash scenarios/scripts/run-m3-after-es-before-offset.sh

scenario-m3-after-dlq:
	bash scenarios/scripts/run-m3-after-dlq-before-offset.sh

scenario-m3:
	bash scenarios/scripts/run-m3-matrix.sh

verify-m3: assert-java-21
	./mvnw -q -pl search-sync-consumer test
	M3_MATRIX_ROUND=1 bash scenarios/scripts/run-m3-matrix.sh
	M3_MATRIX_ROUND=2 bash scenarios/scripts/run-m3-matrix.sh
	bash tests/contracts/m3-completion-gate.sh

gate-m2-m3: verify-m3
	curl -fsS http://127.0.0.1:8082/actuator/health | jq -e '.status == "UP"'
	curl -fsS http://127.0.0.1:8082/actuator/metrics/cdc_es_bulk_items_total | jq -e '.name == "cdc_es_bulk_items_total"'
	curl -fsS http://127.0.0.1:8082/actuator/metrics/cdc_product_dlq_unresolved | jq -e '.measurements[0].value == 0'
	curl -fsS http://127.0.0.1:8082/actuator/metrics/cdc_record_dlq_unresolved | jq -e '.measurements[0].value == 0'
	curl -fsS http://127.0.0.1:8082/internal/dlq/count | jq -e '.unresolved == 0'
	curl -fsS http://127.0.0.1:8082/internal/record-dlq/count | jq -e '.unresolved == 0'
	git diff --check
	@tracked_status="$$(git status --porcelain --untracked-files=no)"; \
	if test -n "$$tracked_status"; then echo "Tracked worktree is not clean:" >&2; echo "$$tracked_status" >&2; exit 1; fi

reconcile:
	curl -fsS -X POST http://127.0.0.1:8083/internal/reconciliation/runs \
	  -H 'Content-Type: application/json' \
	  -d '{"target":"products_write","pageSize":200}'

scenario-m4:
	bash scenarios/scripts/run-m4-reconciliation.sh

verify-m4: assert-java-21
	./mvnw -q -pl consistency-verifier,search-sync-consumer test
	bash tests/contracts/m4-completion-assets.sh
	bash tests/end-to-end/m4-reconciliation.sh
	git diff --check
	@tracked_status="$$(git status --porcelain --untracked-files=no)"; \
	if test -n "$$tracked_status"; then echo "Tracked worktree is not clean after M4 gate:" >&2; echo "$$tracked_status" >&2; exit 1; fi

rebuild:
	@run_id="$$(uuidgen | tr '[:upper:]' '[:lower:]')"; \
	curl -fsS -X POST http://127.0.0.1:8083/internal/rebuild/runs \
	  -H 'Content-Type: application/json' \
	  -d "{\"runId\":\"$$run_id\",\"reason\":\"NORMAL\",\"topic\":\"product-search-revisions\",\"pageSize\":200}"

scenario-m5:
	bash scenarios/scripts/run-m5-rebuild.sh

verify-m5: assert-java-21
	./mvnw -q -pl product-service,search-sync-consumer,consistency-verifier test
	bash tests/contracts/canal-position-recovery.sh
	bash tests/contracts/m5-rebuild-completion-assets.sh
	bash tests/contracts/m5-review-fixes.sh
	bash tests/end-to-end/m5-rebuild.sh
	bash tests/contracts/check-verifier-independence.sh
	git diff --check

formal-final-m5: assert-java-21
	bash scenarios/scripts/run-m5-formal-final.sh
