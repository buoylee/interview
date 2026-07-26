SHELL := /bin/bash
COMPOSE := docker compose -f infra/compose.yaml

.PHONY: assert-java-21 package up down reset verify smoke-m0 evidence

assert-java-21:
	@java -version 2>&1 | head -n 1 | grep -Eq 'version "21([.]|\")' || { \
		echo "Java 21 is required. Set JAVA_HOME to a Temurin 21 installation before running make." >&2; \
		exit 1; \
	}

package: assert-java-21
	./mvnw -q -DskipTests package

up: package
	$(COMPOSE) up -d --build

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
