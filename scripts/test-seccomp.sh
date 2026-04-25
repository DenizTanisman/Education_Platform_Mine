#!/usr/bin/env bash
# Verifies that infra/seccomp.json:
#   1. blocks the extra-deny syscalls (ptrace is the representative check)
#   2. does not break normal Python execution
#
# Run from the repo root:
#   ./scripts/test-seccomp.sh
#
# Prerequisite: iau-sandbox:latest image built (see infra/sandbox.Dockerfile).

set -euo pipefail

IMAGE="iau-sandbox:latest"
PROFILE="$(cd "$(dirname "$0")/.." && pwd)/infra/seccomp.json"

if [ ! -f "$PROFILE" ]; then
  echo "FAIL: seccomp profile not found at $PROFILE" >&2
  exit 2
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "FAIL: image $IMAGE not built. Run: docker build -t $IMAGE -f infra/sandbox.Dockerfile ." >&2
  exit 2
fi

# Python snippet shared by control + sandboxed runs.
# PTRACE_TRACEME (request=0) on one's own process normally succeeds and returns 0.
# With our seccomp deny, the syscall is short-circuited to errno=1 (EPERM).
read -r -d '' PTRACE_PY <<'PY' || true
import ctypes, ctypes.util, platform, sys
libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
libc.syscall.restype = ctypes.c_long
nr = {"x86_64": 101, "aarch64": 117}.get(platform.machine())
if nr is None:
    print(f"UNSUPPORTED_ARCH:{platform.machine()}")
    sys.exit(3)
rv = libc.syscall(nr, 0, 0, 0, 0)
print(f"rv={rv} errno={ctypes.get_errno()}")
PY

echo "== control: ptrace WITHOUT our seccomp (baseline) =="
control_out=$(docker run --rm --entrypoint python "$IMAGE" -c "$PTRACE_PY")
echo "  output: $control_out"
# Baseline: PTRACE_TRACEME on self returns 0 (or at least != -1 with errno=1).
case "$control_out" in
  "rv=0 "*) echo "  baseline OK (ptrace succeeds when unsandboxed)" ;;
  *) echo "WARN: unexpected baseline output — test may be non-authoritative" ;;
esac
echo

echo "== test 1: ptrace WITH seccomp profile (must be BLOCKED) =="
set +e
sandboxed_out=$(docker run --rm \
  --security-opt seccomp="$PROFILE" \
  --entrypoint python \
  "$IMAGE" -c "$PTRACE_PY")
rc=$?
set -e
echo "  output: $sandboxed_out (exit=$rc)"
if [ "$sandboxed_out" != "rv=-1 errno=1" ]; then
  echo "FAIL: ptrace was not blocked (expected 'rv=-1 errno=1')" >&2
  exit 1
fi
echo "  PASS"
echo

echo "== test 2: normal Python WITH seccomp profile (must WORK) =="
normal_out=$(docker run --rm \
  --security-opt seccomp="$PROFILE" \
  --entrypoint python \
  "$IMAGE" -c 'print("hello from sandboxed python")')
echo "  output: $normal_out"
if [ "$normal_out" != "hello from sandboxed python" ]; then
  echo "FAIL: normal python output unexpected" >&2
  exit 1
fi
echo "  PASS"
echo

echo "All seccomp self-tests PASSED."
