# IAU AI Platform — Makefile
#
# Common dev operations for the docker compose stack.
# Assumes a populated `.env` in the project root (copy .env.example first).

.PHONY: start stop logs status reset clean sandbox sandbox-test \
        migrate-build migrate ingest ingest-dry

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

# Build the small image used to run prisma migrations + ingest from outside
# the compose stack. node:20-slim with openssl, no app code baked in.
migrate-build:
	docker build -t iau-app-migrate:latest -f app/Dockerfile.migrate app/

# Apply pending Prisma migrations to the dev database. Brings up postgres
# if it is not already running; needs `.env` for DATABASE_URL.
migrate: migrate-build
	docker compose up -d postgres
	docker run --rm \
	  --network education_platform_internal_net \
	  -v $(PWD)/app:/app -w /app \
	  --env-file .env \
	  iau-app-migrate:latest \
	  npx prisma migrate deploy

# Ingest content/inbox/*.zip into the database. Runs from the HOST (not
# inside a container) because the script spawns the sandbox runner via
# docker, and docker-in-docker would force path-translation for the bind
# mounts. Postgres is reachable on loopback via LOCAL_DATABASE_URL; sandbox
# image is reachable via the local docker daemon.
ingest: sandbox
	docker compose up -d postgres
	cd app && DATABASE_URL=$$(grep '^LOCAL_DATABASE_URL=' ../.env | cut -d= -f2-) \
	  npm run ingest

# --dry-run variant: validates ZIPs and runs the reference solution through
# the sandbox, but does not write to the DB or move any files.
ingest-dry: sandbox
	cd app && DATABASE_URL=$$(grep '^LOCAL_DATABASE_URL=' ../.env | cut -d= -f2-) \
	  npm run ingest:dry-run
