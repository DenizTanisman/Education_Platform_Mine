# IAU AI Platform — Makefile
#
# Common dev operations for the docker compose stack.
# Assumes a populated `.env` in the project root (copy .env.example first).

.PHONY: start stop logs status reset clean sandbox sandbox-test

start:
	docker compose up -d --build

stop:
	docker compose down

logs:
	docker compose logs -f

status:
	docker compose ps

# reset removes containers, networks, AND named volumes (postgres data, caddy data).
# Requires interactive "YES" confirmation to avoid accidental data loss.
reset:
	@echo "WARNING: 'make reset' will DELETE all data volumes (postgres, caddy)."
	@echo "Type YES to confirm, anything else aborts."
	@read -r confirm; \
	if [ "$$confirm" = "YES" ]; then \
		docker compose down -v; \
		echo "Stack and volumes removed."; \
	else \
		echo "Aborted."; \
		exit 1; \
	fi

clean:
	docker compose down --remove-orphans

# Build the sandbox image used to execute student submissions.
# Independent of the compose stack — only docker daemon required.
sandbox:
	docker build -t iau-sandbox:latest -f infra/sandbox.Dockerfile .

# Run the bundled pass / fail / malicious examples through the sandbox.
# Requires `make sandbox` first and runner/ deps installed (cd runner && npm install).
sandbox-test:
	./scripts/test-sandbox.sh pass
	./scripts/test-sandbox.sh fail
	./scripts/test-sandbox.sh malicious
