#!/usr/bin/env bash
# End-to-end sandbox driver: runs an example submission through the hardened
# runner and prints the outcome JSON. See scripts/sandbox-examples/ for the
# canonical pass / fail / malicious cases.
#
# Usage:
#   ./scripts/test-sandbox.sh <example-name|tests-dir> [code-dir]
#
# Forms:
#   ./scripts/test-sandbox.sh pass             # uses scripts/sandbox-examples/pass
#   ./scripts/test-sandbox.sh fail
#   ./scripts/test-sandbox.sh malicious
#   ./scripts/test-sandbox.sh /abs/tests /abs/code   # explicit pair
#
# Requires: docker daemon up, iau-sandbox:latest built, runner deps installed.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SECCOMP="$REPO/infra/seccomp.json"
EXAMPLES="$REPO/scripts/sandbox-examples"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <pass|fail|malicious> | <tests-dir> <code-dir>" >&2
  exit 2
fi

if [ "$#" -eq 1 ]; then
  case "$1" in
    pass|fail|malicious)
      tests_dir="$EXAMPLES/$1/tests"
      code_dir="$EXAMPLES/$1/code"
      ;;
    *)
      echo "unknown example: $1 (expected pass|fail|malicious)" >&2
      exit 2
      ;;
  esac
else
  tests_dir="$1"
  code_dir="$2"
fi

if [ ! -d "$tests_dir" ] || [ ! -d "$code_dir" ]; then
  echo "missing directory: tests='$tests_dir' code='$code_dir'" >&2
  exit 2
fi

if ! docker image inspect iau-sandbox:latest >/dev/null 2>&1; then
  echo "iau-sandbox:latest not built; run: docker build -t iau-sandbox:latest -f infra/sandbox.Dockerfile ." >&2
  exit 2
fi

cd "$REPO/runner"
node --experimental-strip-types --no-warnings=ExperimentalWarning \
  src/cli.ts \
  --tests "$tests_dir" \
  --code "$code_dir" \
  --seccomp "$SECCOMP"
