SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
export PATH := $(CURDIR)/.tools/bin:$(PATH)
export UV_PYTHON := 3.14.10
UV := $(CURDIR)/.tools/bin/uv
.DEFAULT_GOAL := help

.PHONY: help doctor bootstrap local-env check test unit-test integration-test infra-test state-test state-plan-test helm-check verify image security atlantis-test lab-up e2e jenkins-test evidence down
help:
	@echo 'bootstrap | doctor | check | test | infra-test | state-test | state-plan-test | verify | image | lab-up | e2e | security | atlantis-test | jenkins-test | evidence | down'
doctor:
	python3 scripts/doctor.py
bootstrap:
	python3 scripts/bootstrap.py
	$(UV) sync --frozen
local-env:
	python3 scripts/local-env.py
check:
	$(UV) run --frozen ruff check .
	$(UV) run --frozen ruff format --check .
	$(UV) run --frozen python scripts/check-repo.py
	actionlint -config-file .github/actionlint.yaml -shellcheck='' .github/workflows/*.yml
unit-test:
	mkdir -p artifacts
	$(UV) run --frozen pytest tests/harness tests/app -m 'not integration' --junitxml=artifacts/unit-junit.xml
test: local-env
	docker compose --env-file .local/dev.env up -d --wait db
	mkdir -p artifacts
	set -a; source .local/dev.env; set +a; $(UV) run --frozen python -m showcase.migrate
	set -a; source .local/dev.env; set +a; $(UV) run --frozen pytest tests --junitxml=artifacts/junit.xml --cov=showcase --cov-report=xml:artifacts/coverage.xml
integration-test:
	mkdir -p artifacts
	$(UV) run --frozen python -m showcase.migrate
	$(UV) run --frozen pytest tests --junitxml=artifacts/junit.xml --cov=showcase --cov-report=xml:artifacts/coverage.xml
infra-test:
	bash scripts/infra-check.sh
state-test:
	bash scripts/infra-check.sh state-bootstrap
state-plan-test:
	$(UV) run --frozen python scripts/state_plan.py
helm-check:
	bash scripts/lab-check.sh
verify: check test infra-test helm-check
image:
	@revision="$$(git rev-parse HEAD)"; dirty=false; test -z "$$(git status --porcelain)" || dirty=true; \
	docker build --label "org.opencontainers.image.revision=$$revision" --label "io.showcase.dirty=$$dirty" --tag financial-showcase-api:local .
security:
	bash scripts/security.sh
atlantis-test:
	bash scripts/atlantis-smoke.sh
lab-up: doctor local-env
	bash scripts/lab-up.sh
e2e:
	bash scripts/lab-e2e.sh
jenkins-test:
	bash scripts/jenkins-test.sh
evidence:
	$(UV) run --frozen python scripts/evidence.py --gate $(or $(GATE),core)
down:
	bash scripts/lab-down.sh
	docker compose --env-file .local/dev.env down
