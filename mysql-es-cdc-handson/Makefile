SHELL := /bin/bash
COMPOSE := docker compose -f infra/compose.yaml
COMPOSE_ADAPTER := $(COMPOSE) -f infra/compose.adapter.yaml

.PHONY: assert-java-21 package up up-adapter down reset verify smoke-m0 evidence scenario-m1 verify-m1 gate-m1 bootstrap-products-v2 verify-products-v2

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
	$(COMPOSE) down --volumes --remove-orphans

verify: assert-java-21
	bash tests/contracts/m0-layout.sh
	bash tests/contracts/m0-compose.sh
	bash tests/contracts/m0-evidence.sh
	bash tests/contracts/m2-m3-wire-contract.sh
	bash tests/contracts/m2-m3-pipeline-control-schema.sh
	./mvnw -q test
	bash scenarios/scripts/verify-product-transactions.sh

smoke-m0: up
	bash scenarios/scripts/smoke-m0.sh

evidence: package
	bash scenarios/scripts/record-image-digests.sh

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

verify-products-v2:
	bash tests/contracts/m2-m3-elasticsearch-aliases.sh
	bash tests/contracts/m2-m3-bootstrap-fail-closed.sh
	bash scenarios/scripts/verify-products-v2-versioning.sh
