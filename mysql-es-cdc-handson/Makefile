SHELL := /bin/bash
COMPOSE := docker compose -f infra/compose.yaml
COMPOSE_ADAPTER := $(COMPOSE) -f infra/compose.adapter.yaml

.PHONY: assert-java-21 package up up-adapter down reset verify smoke-m0 evidence scenario-m1 verify-m1

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
