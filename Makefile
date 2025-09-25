.PHONY: start stop restart status logs down shutdown ingest cleanDB save push savepush

# Ports
RUNNER_PORT=5050
MGMT_PORT=5051
CRUD_PORT=5052

# Python executables
PYTHON=.venv/bin/python

logs:
	@mkdir -p logs

stop:
	@echo "Stopping services on ports $(RUNNER_PORT), $(MGMT_PORT), $(CRUD_PORT)..."
	-@lsof -ti tcp:$(RUNNER_PORT) | xargs -n 1 kill 2>/dev/null || true
	-@lsof -ti tcp:$(MGMT_PORT)   | xargs -n 1 kill 2>/dev/null || true
	-@lsof -ti tcp:$(CRUD_PORT)   | xargs -n 1 kill 2>/dev/null || true
	@echo "Services stopped."

down: stop
	@echo "All services shut down."

shutdown: down

start: logs
	@echo "Starting Runner-Service (port $(RUNNER_PORT))..."
	@RUNNER_RELOAD=0 nohup $(PYTHON) runner-service/app.py > logs/runner.log 2>&1 &
	@sleep 1
	@echo "Starting Management Studio (port $(MGMT_PORT))..."
	@MGMT_STUDIO_PORT=$(MGMT_PORT) PYTHONPATH=$(PWD):$(PWD)/json-database nohup $(PYTHON) ui-managementstudio/app.py > logs/ui-mgmt.log 2>&1 &
	@sleep 1
	@echo "Starting UI-CRUD (port $(CRUD_PORT))..."
	@nohup $(PYTHON) -m http.server $(CRUD_PORT) -d ui-crud > logs/ui-crud.log 2>&1 &
	@echo "All services started. See logs/ for outputs."

restart:
	@$(MAKE) stop
	@sleep 1
	@$(MAKE) start

status:
	@echo "Runner-Service:"
	-@curl -s http://localhost:$(RUNNER_PORT)/health || true; echo
	@echo "Management Studio:"
	-@curl -sI http://localhost:$(MGMT_PORT)/sql | head -n 1 || true; echo
	@echo "UI-CRUD:"
	-@curl -sI http://localhost:$(CRUD_PORT) | head -n 1 || true; echo

ingest:
	@echo "Starting data ingestion (CSV → Stage0 → Outbox → rawdata)..."
	@source .venv/bin/activate && python ingest_data.py

cleanDB:
	@echo "⚠️  WARNING: This will delete ALL data in the database!"
	@source .venv/bin/activate && python clean_database.py

# --- Git Shortcuts ---

# Usage examples:
#   make save m="feat: add X"        # commit all changes (including untracked)
#   make push                         # push current branch to origin (sets upstream if missing)
#   make savepush m="wip"            # commit all + push

save:
	@git add -A
	@msg="$(if $(m),$(m),chore: savepoint $(shell date '+%Y-%m-%d %H:%M:%S'))" ; \
	 echo "Committing: $$msg" ; \
	 git commit -m "$$msg" || echo "Nothing to commit."

push:
	@branch=$$(git rev-parse --abbrev-ref HEAD) ; \
	 if git rev-parse --abbrev-ref --symbolic-full-name @\{u\} >/dev/null 2>&1; then \
	   echo "Pushing $$branch to tracked upstream..." ; \
	   git push ; \
	 else \
	   echo "Setting upstream and pushing $$branch to origin..." ; \
	   git push -u origin $$branch ; \
	 fi

savepush: save push

