# Cross-platform virtualenv paths (no special shell assumptions)
VENVDIR := .venv
ifdef OS
	ifeq ($(OS),Windows_NT)
		PY := $(VENVDIR)/Scripts/python.exe
	else
		PY := $(VENVDIR)/bin/python
	endif
else
	# POSIX
	PY := $(VENVDIR)/bin/python
endif

# Detect if we're running in Docker (skip venv creation)
IN_DOCKER := $(if $(wildcard /.dockerenv),1,0)
ifeq ($(IN_DOCKER),1)
	PY := python
	SKIP_VENV := 1
endif

# UX: reduce noise from recursive make directory messages
MAKEFLAGS += --no-print-directory

# UX/Defaults
.DEFAULT_GOAL := help

# DRY: centralize common IO paths (overridable via environment/CLI)
INPUT_WEBSITES ?= data/inputs/sample-websites.csv
PY_OUT         ?= data/outputs/python_results.ndjson
NODE_OUT       ?= data/outputs/node_results.ndjson
SCRAPY_OUT     ?= data/outputs/scrapy_results.ndjson
SCRAPY_LITE_OUT ?= data/outputs/scrapy_lite_results.ndjson
REPORT_DIR     ?= data/reports
STAGE_DIR      ?= data/staging

# Configuration profile (optional; for benchmarking different settings)
# Examples: aggressive, conservative, balanced
# Usage: make crawl-python PROFILE=aggressive
PROFILE ?=

# Benchmark configurations (space-separated list of crawler:profile pairs)
# Examples: 
#   make benchmark BENCH_CONFIGS="python:aggressive scrapy:balanced"
#   make benchmark BENCH_CONFIGS="python:aggressive python:conservative scrapy:aggressive"
# Default: runs all three crawlers with default profile
BENCH_CONFIGS ?=

# Build profile argument if PROFILE is set
ifdef PROFILE
	PROFILE_ARG := --profile $(PROFILE)
else
	PROFILE_ARG :=
endif

# Elasticsearch defaults (overridable)
ES_URL   ?= http://localhost:9200
ES_INDEX ?= companies_v1
ES_ALIAS ?= companies

# API URL (use service name when in Docker, localhost otherwise)
API_URL ?= http://localhost:8000
ifeq ($(IN_DOCKER),1)
	API_URL := http://phidi:8000
	ES_URL := http://elasticsearch:9200
endif

# DRY: Common patterns and helper functions
# Usage: $(call docker-or-local,target-name)
define docker-or-local
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	$(1)
else
	@docker compose run --rm runner make $(2) PROFILE=$(PROFILE)
endif
endef

# DRY: Profile notification helper
define show-profile
	@if [ -n "$(PROFILE)" ]; then echo "[$(1)] Using profile: $(PROFILE)"; fi
endef

# DRY: helper for Scrapy-family crawlers
define run-scrapy-crawler-docker
	@$(MAKE) venv
	@echo "[$(2)] Running $(3)..."
	$(call show-profile,$(4))
	@"$(PY)" -m pip install -q -r $(5)
	@"$(PY)" $(6) --input "$(INPUT_WEBSITES)" --output "$(7)" $(PROFILE_ARG)
endef

define run-scrapy-crawler-compose
	@docker compose run --rm runner make $(1) PROFILE=$(PROFILE)
endef

define run-scrapy-crawler
$(if $(filter 1,$(IN_DOCKER)),$(call run-scrapy-crawler-docker,$(1),$(2),$(3),$(4),$(5),$(6),$(7)),$(call run-scrapy-crawler-compose,$(1)))
endef

# DRY: Common evaluation arguments
EVAL_ARGS = --websites "$(INPUT_WEBSITES)" --out-dir "$(REPORT_DIR)"
SELECT_ARGS = --metrics "$(REPORT_DIR)/metrics.csv" --out-dir "$(STAGE_DIR)" --coverage-weight 0.6 --quality-weight 0.4

.PHONY: help venv test test-python test-node coverage coverage-python coverage-node clean clean-crawler clean-etl clean-node metrics evaluate crawl crawl-all crawl-python crawl-node crawl-python-pipeline crawl-node-pipeline crawl-all-pipeline crawl-pipeline select etl run use-python use-node benchmark logs logs-api logs-es

# Lightweight preflight checks (no external tools; cross-platform)
ifeq ($(OS),Windows_NT)
.PHONY: check
check:
	@echo "[CHECK] Verifying inputs..."
	@if not exist "$(INPUT_WEBSITES)" ( echo [ERROR] Missing input: $(INPUT_WEBSITES) & exit 1 )
	@echo "[CHECK] OK"
else
.PHONY: check
check:
	@echo "[CHECK] Verifying inputs..."
	@test -f "$(INPUT_WEBSITES)" || (echo "[ERROR] Missing input: $(INPUT_WEBSITES)"; exit 1)
	@echo "[CHECK] OK"
endif

help:
	@echo "Targets:"
	@echo "  # Testing"
	@echo "  -------------------------------"
	@echo "  make test            # Run all tests (Python + Node)"
	@echo "  make test-python     # Run Python tests"
	@echo "  make test-node       # Run Node (mocha) tests"
	@echo "  make coverage        # Run coverage for both stacks"
	@echo "  make coverage-python # Python coverage"
	@echo "  make coverage-node   # Node (nyc) coverage"
	@echo "  make smoke-es        # Quick check: ping ES, count docs, print a few sample records"
	@echo "  make smoke-api       # Quick check: call /healthz and a sample /match request"
	@echo "  -------------------------------"
	@echo "  "
	@echo "  # Docker"
	@echo "  -------------------------------"
	@echo "  make up              # docker compose up -d (starts ES + Kibana + API)"
	@echo "  make down            # docker compose down"
	@echo "  make reset           # docker compose down -v (remove volumes)"
	@echo "  make status          # docker compose ps"
	@echo "  make logs            # Follow all service logs"
	@echo "  make logs-api        # Follow API logs only"
	@echo "  make logs-es         # Follow Elasticsearch logs only"
	@echo "  "
	@echo "  # Main commands"
	@echo "  -------------------------------"
	@echo "  ## Cleanup"
	@echo "  "
	@echo "  make clean           	# Remove Stage 1/2 generated files and clear Elasticsearch documents"
	@echo "  make clean-crawler    	# Remove Stage 1 generated files only"
	@echo "  make clean-etl    		# Remove Stage 2 ETL outputs from data/staging"
	@echo "  make clean-es        	# Delete ES indices behind alias $(ES_ALIAS) (or $(ES_INDEX) if alias missing)"
	@echo "  "
	@echo "  ## Stage 1: Crawling & Evaluation"
	@echo "  "
	@echo "  make metrics         # Compute crawl coverage & fill rates (Stage 1.2)"
	@echo "  make evaluate        # Run Stage 1.2 evaluation (CSV + Markdown reports)"
	@echo "  make crawl           # Run Python pipeline (default); see 'crawl-*' targets for more options"
	@echo "  make crawl-python    # Run Python crawler only (no eval/select)"
	@echo "  make crawl-node      # Run Node crawler only (no eval/select)"
	@echo "  make crawl-scrapy    # Run Scrapy crawler (native extraction) only"
	@echo "  make crawl-scrapy-lite # Run Scrapy-lite crawler (regex extraction) only"
	@echo "  make select          # Stage 1.3: choose best dataset and stage it"
	@echo "  "
	@echo "  ## Configuration Profiles (optional)"
	@echo "  "
	@echo "  make crawl-python PROFILE=aggressive     # Run with aggressive profile"
	@echo "  make crawl-node PROFILE=conservative     # Run with conservative profile"
	@echo "  make crawl-scrapy PROFILE=balanced       # Run with balanced profile"
	@echo "  make crawl-scrapy-lite PROFILE=balanced  # Run scrapy-lite with balanced profile"
	@echo "  "
	@echo "  Available profiles: aggressive (fast), conservative (thorough), balanced (default)"
	@echo "  See configs/profiles/README.md for details"
	@echo "  "
	@echo "  ## Stage 2: ETL & Loading"
	@echo "  "
	@echo "  make api-start       # Start FastAPI server (uvicorn) on http://localhost:8000"
	@echo "  make api-batch-eval  # Batch-evaluate /match over CSV and write reports (CSV, JSON, Markdown)"
	@echo "  "
	@echo "  # Main pipeline"
	@echo "  -------------------------------"
	@echo "  make crawl-python-pipeline  # Stage 1 with Python crawler only"
	@echo "  make crawl-node-pipeline    # Stage 1 with Node crawler only"
	@echo "  make crawl-scrapy-pipeline  # Stage 1 with Scrapy crawler (native) only"
	@echo "  make crawl-scrapy-lite-pipeline # Stage 1 with Scrapy-lite crawler (regex) only"
	@echo "  make crawl-all-pipeline     # Stage 1 with both crawlers (alias: crawl-pipeline)"
	@echo "  make benchmark              # Full benchmark: crawl -> evaluate -> select -> ETL -> API eval (default: all 3) or custom: BENCH_CONFIGS=\"python:aggressive scrapy:balanced\""
	@echo "  make etl                    # Run Stage 2.1 ETL: normalize -> merge_names -> dedupe -> load_es (indexes by default; use 'make etl-dry-run' to validate)"
	@echo "  make api			  		 # Run Stage 2.2 API: start server and batch-evaluate inputs -> reports"
	@echo "  "
	@echo "  # End-to-end workflows"
	@echo "  -------------------------------"
	@echo "  make run         # Full workflow: clean -> Python pipeline -> ETL -> API eval (DEFAULT)"
	@echo "  make use-python  # Full workflow with Python crawler"
	@echo "  make use-node    # Full workflow with Node crawler"
	@echo "  make use-scrapy  # Full workflow with Scrapy crawler (native extraction)"
	@echo "  make use-scrapy-lite # Full workflow with Scrapy-lite crawler (regex extraction)"
	@echo "  make demo		  # Spin up docker and run a demo of the default full workflow"

venv:
ifndef SKIP_VENV
	@echo [PY] Ensuring virtualenv...
ifeq ($(OS),Windows_NT)
	@if not exist "$(VENVDIR)\Scripts\python.exe" ( python -m venv "$(VENVDIR)" ) else ( echo [PY] Reusing existing venv )
else
	@test -x "$(VENVDIR)/bin/python" || python -m venv "$(VENVDIR)"
endif
	@"$(PY)" -m pip install -q -U pip pytest
else
	@echo [PY] Running in Docker, skipping venv...
endif

test: test-python test-node

test-python:
ifeq ($(IN_DOCKER),1)
	@echo "[PY] Running Python tests..."
	@"$(PY)" -m pytest tests/ -q
else
	@docker compose run --rm runner make $@
endif

test-node:
ifeq ($(IN_DOCKER),1)
	@echo "[JS] Running Node tests..."
	@cd src/crawlers/node && npm ci && npm run build && npm test
else
	@docker compose run --rm runner make $@
endif

coverage: coverage-python coverage-node

coverage-python:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[PY] Coverage..."
	@"$(PY)" -m pip install -q pytest-cov jsonschema || true
	@"$(PY)" -m pytest tests/ --cov=src --cov-report=term-missing
else
	@docker compose run --rm runner make $@
endif

coverage-node:
ifeq ($(IN_DOCKER),1)
	@echo "[JS] Coverage..."
	@cd src/crawlers/node && npm ci && npm run build && npm run test:coverage
else
	@docker compose run --rm runner make $@
endif

clean-node:
ifeq ($(IN_DOCKER),1)
	@cd src/crawlers/node && npm run clean || true
else
	@docker compose run --rm runner make $@
endif

.PHONY: up down reset status logs logs-api logs-es
up:
	@docker compose up -d

down:
	@docker compose down

reset:
	@docker compose down -v

status:
	@docker compose ps

logs:
	@docker compose logs -f

logs-api:
	@docker compose logs -f api

logs-es:
	@docker compose logs -f elasticsearch

metrics:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[EVAL] Computing coverage & fill rates..."
	@"$(PY)" src/eval/compute_metrics.py \
		--input "$(INPUT_WEBSITES)" \
		--results python:"$(PY_OUT)" node:"$(NODE_OUT)" scrapy:"$(SCRAPY_OUT)" scrapy-lite:"$(SCRAPY_LITE_OUT)" \
		--csv-out "$(REPORT_DIR)/metrics.csv" \
		--md-out "$(REPORT_DIR)/summary.md"
else
	@docker compose run --rm runner make $@
endif

evaluate:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[EVAL] Running Stage 1.2 evaluation..."
	@"$(PY)" src/eval/evaluate.py --websites "$(INPUT_WEBSITES)" \
		--results python:"$(PY_OUT)" node:"$(NODE_OUT)" scrapy:"$(SCRAPY_OUT)" scrapy-lite:"$(SCRAPY_LITE_OUT)" \
		$(EVAL_ARGS)
else
	@docker compose run --rm runner make $@
endif

# Default crawl target: run Python pipeline (most common use case)
crawl:
	@$(MAKE) crawl-python-pipeline

# Individual crawler targets (just crawling, no eval/select)
crawl-all: crawl-python crawl-node crawl-scrapy crawl-scrapy-lite

crawl-python: check
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[PY] Running Python crawler..."
	$(call show-profile,PY)
	@"$(PY)" src/crawlers/python/main.py --input "$(INPUT_WEBSITES)" --output "$(PY_OUT)" $(PROFILE_ARG)
else
	@docker compose run --rm runner make $@ PROFILE=$(PROFILE)
endif

crawl-node:
ifeq ($(IN_DOCKER),1)
	@echo "[JS] Running Node crawler..."
	$(call show-profile,JS)
	@cd src/crawlers/node && npm ci && npm run build && node dist/index.js --input "/app/$(INPUT_WEBSITES)" --output "/app/$(NODE_OUT)" $(PROFILE_ARG)
else
	@docker compose run --rm runner make $@ PROFILE=$(PROFILE)
endif

crawl-scrapy: check
	$(call run-scrapy-crawler,crawl-scrapy,SCRAPY,Scrapy crawler (native extraction),SCRAPY,src/crawlers/scrapy/requirements.txt,src/crawlers/scrapy/main.py,$(SCRAPY_OUT))

crawl-scrapy-lite: check
	$(call run-scrapy-crawler,crawl-scrapy-lite,SCRAPY-LITE,Scrapy-lite crawler (regex extraction),SCRAPY_LITE,src/crawlers/scrapy-lite/requirements.txt,src/crawlers/scrapy-lite/main.py,$(SCRAPY_LITE_OUT))

# Pipeline targets: crawl + evaluate + select for specific crawler(s)
# DRY: Common pipeline steps
define run-pipeline
	@echo "[$(1)] Running Stage 1 pipeline with $(2) crawler$(3)"
	@$(MAKE) crawl-$(4)
	@"$(PY)" src/eval/evaluate.py $(EVAL_ARGS) --results $(5)
	@"$(PY)" src/selector/choose_dataset.py $(SELECT_ARGS) --outputs $(5)
	@echo "[$(1)] Complete. Staged: $(STAGE_DIR)/crawl_results.ndjson"
	@echo "[NEXT] Run 'make etl' to continue with Stage 2"
endef

crawl-python-pipeline: check
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	$(call run-pipeline,STAGE1-PY,Python,,python,python:"$(PY_OUT)")
else
	@docker compose run --rm runner make $@ PROFILE=$(PROFILE)
endif

crawl-node-pipeline: check
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	$(call run-pipeline,STAGE1-JS,Node,,node,node:"$(NODE_OUT)")
else
	@docker compose run --rm runner make $@ PROFILE=$(PROFILE)
endif

crawl-scrapy-pipeline: check
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	$(call run-pipeline,STAGE1-SCRAPY,Scrapy (native),,scrapy,scrapy:"$(SCRAPY_OUT)")
else
	@docker compose run --rm runner make $@ PROFILE=$(PROFILE)
endif

crawl-scrapy-lite-pipeline: check
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	$(call run-pipeline,STAGE1-SCRAPY-LITE,Scrapy-lite (regex),,scrapy-lite,scrapy-lite:"$(SCRAPY_LITE_OUT)")
else
	@docker compose run --rm runner make $@ PROFILE=$(PROFILE)
endif

crawl-all-pipeline: check
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[STAGE1] Running Stage 1 pipeline with all crawlers"
	@$(MAKE) crawl-all
	@"$(PY)" src/eval/evaluate.py --websites "$(INPUT_WEBSITES)" \
		--out-dir "$(REPORT_DIR)"
	@"$(PY)" src/selector/choose_dataset.py \
		--metrics "$(REPORT_DIR)/metrics.csv" \
		--out-dir "$(STAGE_DIR)" --coverage-weight 0.6 --quality-weight 0.4
	@echo "[STAGE1] Complete."
	@echo "[STAGE1] Reports:     $(REPORT_DIR)"
	@echo "[STAGE1] Staged data: $(STAGE_DIR)"
	@echo "[NEXT] To continue with Stage 2 (ETL), run: make etl"
	@echo "[NEXT] ETL will index into Elasticsearch by default. For a validation-only run, use: make etl-dry-run"
	@echo "[NEXT] Tip: View the comparison report at $(REPORT_DIR)/summary.md and metrics at $(REPORT_DIR)/metrics.csv"
else
	@docker compose run --rm runner make crawl-all-pipeline
endif

# Alias for backward compatibility
crawl-pipeline: crawl-all-pipeline

# Benchmark: flexible crawler comparison with custom configurations
# Usage:
#   make benchmark                                                    # Run all 3 crawlers (default)
#   make benchmark BENCH_CONFIGS="python:aggressive scrapy:balanced"  # Custom comparison
#   make benchmark BENCH_CONFIGS="python:aggressive python:conservative node:aggressive"  # Multiple profiles per crawler
benchmark: check
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[BENCHMARK] Starting crawler benchmark..."
ifeq ($(strip $(BENCH_CONFIGS)),)
	@echo "[BENCHMARK] Using default: all crawlers with default profile"
	@$(MAKE) crawl-all-pipeline
	@echo "[BENCHMARK] Running ETL pipeline..."
	@$(MAKE) etl
	@echo "[BENCHMARK] Running API batch evaluation..."
	@$(MAKE) api-batch-eval
	@echo "[BENCHMARK] Complete."
	@echo "[BENCHMARK] Reports:     $(REPORT_DIR)"
	@echo "[BENCHMARK] API reports: $(REPORT_DIR)/api_match_*.{csv,json,md}"
else
	@echo "[BENCHMARK] Custom configurations: $(BENCH_CONFIGS)"
	@$(MAKE) _benchmark-run
endif
else
	@docker compose run --rm runner make benchmark BENCH_CONFIGS="$(BENCH_CONFIGS)"
endif

# Internal target: run custom benchmark configurations
.PHONY: _benchmark-run
_benchmark-run:
	@echo "[BENCHMARK] Running custom crawler configurations..."
	@$(MAKE) _benchmark-crawl
	@echo "[BENCHMARK] Evaluating results..."
	@$(MAKE) _benchmark-eval
	@echo "[BENCHMARK] Selecting best dataset..."
	@$(MAKE) _benchmark-select
	@echo "[BENCHMARK] Running ETL pipeline..."
	@$(MAKE) etl
	@echo "[BENCHMARK] Running API batch evaluation..."
	@$(MAKE) api-batch-eval
	@echo "[BENCHMARK] Complete."
	@echo "[BENCHMARK] Reports:     $(REPORT_DIR)"
	@echo "[BENCHMARK] Staged data: $(STAGE_DIR)"
	@echo "[BENCHMARK] API reports: $(REPORT_DIR)/api_match_*.{csv,json,md}"

# Internal: run all configured crawlers
.PHONY: _benchmark-crawl
_benchmark-crawl:
	@for config in $(BENCH_CONFIGS); do \
		crawler=$$(echo $$config | cut -d: -f1); \
		profile=$$(echo $$config | cut -d: -f2); \
		output_suffix=""; \
		case $$crawler in \
			python) output_var=PY_OUT; output_path="data/outputs/python_results";; \
			node) output_var=NODE_OUT; output_path="data/outputs/node_results";; \
			scrapy) output_var=SCRAPY_OUT; output_path="data/outputs/scrapy_results";; \
			scrapy-lite) output_var=SCRAPY_LITE_OUT; output_path="data/outputs/scrapy_lite_results";; \
			*) echo "[BENCHMARK] Unknown crawler: $$crawler"; exit 1;; \
		esac; \
		if [ -n "$$profile" ] && [ "$$profile" != "$$crawler" ]; then \
			output_suffix="_$$profile"; \
			echo "[BENCHMARK] Running $$crawler with profile: $$profile"; \
			$(MAKE) crawl-$$crawler PROFILE=$$profile $$output_var="$$output_path$$output_suffix.ndjson"; \
		else \
			echo "[BENCHMARK] Running $$crawler with default profile"; \
			$(MAKE) crawl-$$crawler; \
		fi; \
	done

# Internal: evaluate all benchmark results
.PHONY: _benchmark-eval
_benchmark-eval:
	@result_args=""; \
	for config in $(BENCH_CONFIGS); do \
		crawler=$$(echo $$config | cut -d: -f1); \
		profile=$$(echo $$config | cut -d: -f2); \
		output_suffix=""; \
		label="$$crawler"; \
		if [ -n "$$profile" ] && [ "$$profile" != "$$crawler" ]; then \
			output_suffix="_$$profile"; \
			label="$$crawler-$$profile"; \
		fi; \
		case $$crawler in \
			python) result_args="$$result_args $$label:data/outputs/python_results$$output_suffix.ndjson";; \
			node) result_args="$$result_args $$label:data/outputs/node_results$$output_suffix.ndjson";; \
			scrapy) result_args="$$result_args $$label:data/outputs/scrapy_results$$output_suffix.ndjson";; \
			scrapy-lite) result_args="$$result_args $$label:data/outputs/scrapy_lite_results$$output_suffix.ndjson";; \
			*) echo "[BENCHMARK] Unknown crawler: $$crawler"; exit 1;; \
		esac; \
	done; \
	"$(PY)" src/eval/evaluate.py $(EVAL_ARGS) --results $$result_args

# Internal: select best from benchmark results
.PHONY: _benchmark-select
_benchmark-select:
	@output_args=""; \
	for config in $(BENCH_CONFIGS); do \
		crawler=$$(echo $$config | cut -d: -f1); \
		profile=$$(echo $$config | cut -d: -f2); \
		output_suffix=""; \
		label="$$crawler"; \
		if [ -n "$$profile" ] && [ "$$profile" != "$$crawler" ]; then \
			output_suffix="_$$profile"; \
			label="$$crawler-$$profile"; \
		fi; \
		case $$crawler in \
			python) output_args="$$output_args $$label:data/outputs/python_results$$output_suffix.ndjson";; \
			node) output_args="$$output_args $$label:data/outputs/node_results$$output_suffix.ndjson";; \
			scrapy) output_args="$$output_args $$label:data/outputs/scrapy_results$$output_suffix.ndjson";; \
			scrapy-lite) output_args="$$output_args $$label:data/outputs/scrapy_lite_results$$output_suffix.ndjson";; \
			*) echo "[BENCHMARK] Unknown crawler: $$crawler"; exit 1;; \
		esac; \
	done; \
	"$(PY)" src/selector/choose_dataset.py $(SELECT_ARGS) --outputs $$output_args

select:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[SEL] Choosing best dataset and staging..."
	@"$(PY)" src/selector/choose_dataset.py $(SELECT_ARGS) \
		--outputs python:"$(PY_OUT)" node:"$(NODE_OUT)" scrapy:"$(SCRAPY_OUT)" scrapy-lite:"$(SCRAPY_LITE_OUT)"
else
	@docker compose run --rm runner make $@
endif

etl:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[ETL] Step 1: normalize"
	@"$(PY)" src/etl/normalize.py --input data/staging/crawl_results.ndjson --output data/staging/crawl_results_normalized.ndjson
	@echo "[ETL] Step 2: merge names"
	@"$(PY)" src/etl/merge_names.py --input data/staging/crawl_results_normalized.ndjson --names data/inputs/sample-websites-company-names.csv --output data/staging/crawl_results_merged.ndjson
	@echo "[ETL] Step 3: dedupe"
	@"$(PY)" src/etl/dedupe.py --input data/staging/crawl_results_merged.ndjson --output data/staging/companies_serving.ndjson
	@echo "[ETL] Step 4: load to Elasticsearch (default: index; for validation use 'make etl-dry-run')"
	@$(MAKE) etl-load
else
	@docker compose up -d
	@docker compose run --rm runner make etl
endif

.PHONY: etl-dry-run etl-load
etl-dry-run:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@"$(PY)" src/etl/load_es.py --input data/staging/companies_serving.ndjson --dry-run
else
	@docker compose run --rm runner make $@
endif

etl-load:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[ETL] Ensuring Elasticsearch Python client..."
	@"$(PY)" -m pip install -q "elasticsearch>=8,<9" || (echo "[ETL] Failed to install 'elasticsearch' package" && exit 1)
	@"$(PY)" src/etl/load_es.py --input data/staging/companies_serving.ndjson --index "$(ES_INDEX)" --alias "$(ES_ALIAS)" --mappings configs/es.mappings.json --es "$(ES_URL)"
else
	@docker compose run --rm runner make $@
endif

.PHONY: smoke-es
smoke-es:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[ES] Smoke test (ping, count, sample)..."
	@"$(PY)" -m pip install -q "elasticsearch>=8,<9" || true
	@"$(PY)" scripts/es_smoke.py --es "$(ES_URL)" --index "$(ES_INDEX)" --alias "$(ES_ALIAS)" --size 5
else
	@docker compose run --rm runner make $@
endif

.PHONY: api api-deps

# Helper: include API_DEBUG only if provided to make; otherwise don't override shell env
ifneq ($(strip $(API_DEBUG)),)
API_DEBUG_ENV := API_DEBUG=$(API_DEBUG)
API_DEBUG_WIN := set API_DEBUG=$(API_DEBUG) &
else
API_DEBUG_ENV :=
API_DEBUG_WIN :=
endif

# api-debug then api-batch-eval
api: export FORCE_COLOR=1
api:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) api-debug
	@$(MAKE) api-batch-eval
	@echo "[API] To stop the API server, press Ctrl+C"
else
	@docker compose up -d api
	@docker compose run --rm runner make api-batch-eval
	@echo "[API] API container is running (service 'api'). Stop via 'make down' when finished."
endif

api-start:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@$(MAKE) api-deps
	@echo "[API] Starting FastAPI (uvicorn) at http://localhost:8000 ..."
	@ES_URL=$(ES_URL) ES_INDEX=$(ES_INDEX) ES_ALIAS=$(ES_ALIAS) $(API_DEBUG_ENV) "$(PY)" -m uvicorn src.api.app:get_uvicorn_app --host 0.0.0.0 --port 8000 --reload
else
	@docker compose up api
endif

api-deps:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[API] Installing requirements..."
	@"$(PY)" -m pip install -q -r src/api/requirements.txt || (echo "[API] Failed to install dependencies" && exit 1)
else
	@docker compose run --rm runner make $@
endif

.PHONY: api-debug
api-debug:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@$(MAKE) api-deps
	@echo "[API] Starting FastAPI (uvicorn) at http://localhost:8000 with debug ..."
	@"$(PY)" -c "import os, uvicorn; os.environ.update({'API_DEBUG':'1','ES_URL':'$(ES_URL)','ES_INDEX':'$(ES_INDEX)','ES_ALIAS':'$(ES_ALIAS)'}); uvicorn.run('src.api.app:get_uvicorn_app', host='0.0.0.0', port=8000, reload=True)"
else
	@docker compose up api
endif

.PHONY: smoke-api
smoke-api:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@$(MAKE) api-deps
	@echo "[API] Smoke test..."
	@API_URL=http://localhost:8000 "$(PY)" scripts/api_smoke.py
else
	@docker compose run --rm runner make $@
endif

.PHONY: api-batch-eval
api-batch-eval:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@$(MAKE) api-deps
	@echo "[API] Batch evaluating inputs -> reports ..."
	@API_URL=$(API_URL) "$(PY)" scripts/api_batch_eval.py --input data/inputs/api-input-sample.csv --csv-out data/reports/api_match_results.csv --summary-out data/reports/api_match_summary.json --report-out data/reports/api_match_report.md
else
	@docker compose run --rm runner make $@
endif

clean: export FORCE_COLOR=1
clean:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[CLEAN] Removing Stage 1 & Stage 2 generated files..."
	@$(MAKE) clean-crawler
	@$(MAKE) clean-etl
	@$(MAKE) clean-es
	@echo [CLEAN] Done.
else
	@docker compose up -d
	@docker compose run --rm runner make clean
endif

clean-crawler: export FORCE_COLOR=1
clean-crawler:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo [CLEAN] Removing Stage 1 generated files...
	@"$(PY)" scripts/clean_stage1.py
else
	@docker compose run --rm runner make $@
endif

clean-etl: export FORCE_COLOR=1
clean-etl:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo [CLEAN] Removing Stage 2 ETL outputs...
	@"$(PY)" scripts/clean_stage2.py
else
	@docker compose run --rm runner make $@
endif

.PHONY: clean-es
clean-es:
ifeq ($(IN_DOCKER),1)
	@$(MAKE) venv
	@echo "[ES] Deleting Elasticsearch documents (indices behind alias '$(ES_ALIAS)' or index '$(ES_INDEX)')..."
	@"$(PY)" -m pip install -q "elasticsearch>=8,<9" || true
	@"$(PY)" scripts/es_clean.py --es "$(ES_URL)" --index "$(ES_INDEX)" --alias "$(ES_ALIAS)"
else
	@docker compose run --rm runner make $@
endif

# End-to-end run workflows: clean -> crawl -> ETL -> API evaluation
# DRY: Common workflow steps
define run-workflow
	@echo "[$(1)] Running full workflow with $(2) crawler$(3)"
	@$(MAKE) clean
	@$(MAKE) crawl-$(4)-pipeline
	@$(MAKE) etl
	@$(MAKE) api-batch-eval
	@echo "[$(1)] Complete! Results in data/reports/api_match_*.{csv,json,md}"
endef

run: export FORCE_COLOR=1
run:
	@echo "[MATCH] Running full workflow with Python crawler (clean -> crawl -> ETL -> API eval)"
	@$(MAKE) clean
	@$(MAKE) crawl
	@$(MAKE) etl
	@$(MAKE) api-batch-eval
	@echo "[MATCH] Complete! Results in data/reports/api_match_*.{csv,json,md}"

# Containerized versions (run in Docker)
use-python: export FORCE_COLOR=1
use-python:
ifeq ($(IN_DOCKER),1)
	$(call run-workflow,MATCH-PY,Python, (in container),python)
else
	@echo "[MATCH-PY] Running containerized workflow with Python crawler..."
	@docker compose up -d
	@docker compose run --rm runner make $@
	@echo "[MATCH-PY] Complete! Results in data/reports/"
endif

use-node: export FORCE_COLOR=1
use-node:
ifeq ($(IN_DOCKER),1)
	$(call run-workflow,MATCH-JS,Node, (in container),node)
else
	@echo "[MATCH-JS] Running containerized workflow with Node crawler..."
	@docker compose up -d
	@docker compose run --rm runner make $@
	@echo "[MATCH-JS] Complete! Results in data/reports/"
endif

use-scrapy: export FORCE_COLOR=1
use-scrapy:
ifeq ($(IN_DOCKER),1)
	$(call run-workflow,MATCH-SCRAPY,Scrapy (native), (in container),scrapy)
else
	@echo "[MATCH-SCRAPY] Running containerized workflow with Scrapy crawler (native extraction)..."
	@docker compose up -d
	@docker compose run --rm runner make $@
	@echo "[MATCH-SCRAPY] Complete! Results in data/reports/"
endif

use-scrapy-lite: export FORCE_COLOR=1
use-scrapy-lite:
ifeq ($(IN_DOCKER),1)
	$(call run-workflow,MATCH-SCRAPY-LITE,Scrapy-lite (regex), (in container),scrapy-lite)
else
	@echo "[MATCH-SCRAPY-LITE] Running containerized workflow with Scrapy-lite crawler (regex extraction)..."
	@docker compose up -d
	@docker compose run --rm runner make $@
	@echo "[MATCH-SCRAPY-LITE] Complete! Results in data/reports/"
endif

demo: export FORCE_COLOR=1
demo:
	@echo "[DEMO] Starting containers (Elasticsearch, Kibana, API)..."
	@docker compose up -d --build
	@echo "[DEMO] Waiting for Elasticsearch to be healthy..."
	@docker compose exec -T elasticsearch curl -sf http://localhost:9200/_cluster/health?wait_for_status=yellow&timeout=60s > /dev/null 2>&1 || echo "[DEMO] Elasticsearch ready"
	@echo "[DEMO] Running tests in container..."
	@docker compose run --rm runner make test
	@echo "[DEMO] Running full workflow in container..."
	@docker compose run --rm runner make run
	@echo "[DEMO] Complete! API is running at http://localhost:8000"
	@echo "[DEMO] View results in data/reports/"
	@echo "[DEMO] To stop services: make down"
