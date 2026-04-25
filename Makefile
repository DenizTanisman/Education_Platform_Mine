# IAU AI Platform — Makefile
#
# Common dev operations for the docker compose stack.
# Assumes a populated `.env` in the project root (copy .env.example first).

.PHONY: start stop logs status reset clean

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
