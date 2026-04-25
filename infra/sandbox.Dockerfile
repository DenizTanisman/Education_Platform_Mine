# IAU AI Platform — Sandbox image for running student submissions
#
# Built once, reused for every submission. At run time (Faz 2.4) the runner
# bind-mounts the extracted submission + test_runner.py under /workspace.
# The real harness.py (Faz 2.3) will be baked in at /workspace/harness.py —
# in 2.1 it is intentionally absent so this task stays scoped to the image.
#
# Security baseline (tightened further by docker run flags in Faz 2.4):
#   - non-root user (uid 1001) — no root privileges inside the container
#   - no build toolchain in the final image — nothing to compile or install
#   - pip cache disabled — image stays small, no leftover metadata
#
# Self-test:
#   docker build -t iau-sandbox:latest -f infra/sandbox.Dockerfile .
#   docker run --rm --entrypoint python iau-sandbox:latest --version
#     -> Python 3.11.x

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Minimal runtime deps for test execution + common student-code patterns.
# Pinned so rebuilds are reproducible; bumped explicitly when we want them.
RUN pip install --no-cache-dir \
        pytest==8.3.3 \
        pydantic==2.9.2 \
        anthropic==0.39.0

# Non-root runtime user (00_MASTER_PROMPT.md §2.4 requires uid 1001).
# nologin shell = no interactive sessions possible. uid 1001 is in the regular
# (not --system) range, so --system would warn about SYS_UID_MAX=999.
RUN groupadd --gid 1001 sandbox \
 && useradd --uid 1001 --gid sandbox --no-create-home \
            --home-dir /workspace --shell /usr/sbin/nologin sandbox \
 && mkdir -p /workspace \
 && chown -R sandbox:sandbox /workspace

WORKDIR /workspace
USER sandbox

# Entrypoint per 01_BUILD_PLAN.md §2.1. harness.py is provided in Faz 2.3;
# until then the default CMD will fail at runtime (expected), but the image
# still builds and `--entrypoint python` overrides work for self-test.
ENTRYPOINT ["python", "/workspace/harness.py"]
