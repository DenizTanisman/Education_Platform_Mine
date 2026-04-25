# Sandbox Security Self-Test Report

End-to-end verification that a hostile student submission cannot escape the
container. Layered defences:

1. `infra/sandbox.Dockerfile` — non-root uid 1001 user, no build toolchain.
2. `infra/seccomp.json` — moby v27.3.1 default + extra denies (`ptrace`,
   `unshare`, `mount`, `umount`/`umount2`, `keyctl`, `bpf`, `userfaultfd`,
   `clone3`, `reboot`).
3. `runner/src/sandbox-runner.ts` — `docker run` flags
   (`--network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges
   --security-opt seccomp=… --pids-limit=64 --memory=512m --memory-swap=512m
   --cpus=0.5 --tmpfs /tmp:rw,noexec,nosuid,size=64m`).
4. Detached watchdog → `docker kill` after the wall-clock budget.
5. `harness.py` — outer + per-test SIGALRM timeouts inside the container.

## How to reproduce

```bash
make start                       # not required for sandbox tests
docker build -t iau-sandbox:latest -f infra/sandbox.Dockerfile .
cd runner && npm install && cd ..

./scripts/test-sandbox.sh pass        # expect verdict=passed
./scripts/test-sandbox.sh fail        # expect verdict=failed (clean diff)
./scripts/test-sandbox.sh malicious   # expect 3/3 escape attempts contained
```

The CLI emits a single JSON object on stdout. `kind="ok"` means the harness
ran to completion; `kind="timeout"` means the watchdog killed the container.

## Threat → mitigation matrix

| Threat | Mitigation | Verified by |
|--------|------------|-------------|
| Outbound network exfiltration | `--network=none` | `malicious/test_network_blocked` (URLError) |
| Read host filesystem outside the bind mounts | `--read-only` rootfs + bind mounts mounted `:ro` | `malicious/test_readonly_blocked` (OSError on `/etc/`) |
| Trace another process / dump memory | seccomp `ptrace` ERRNO + `--cap-drop=ALL` | `malicious/test_ptrace_blocked` (rv=-1) |
| Fork bomb / runaway children | `--pids-limit=64` + `--cpus=0.5` | `runner/tests/...` integration test (BlockingIOError or watchdog) |
| Memory hog | `--memory=512m` `--memory-swap=512m` | OOM kill (Linux kernel); reproducible by allocating > 512 MB |
| Privilege escalation via setuid/file caps | `--security-opt=no-new-privileges` + `--cap-drop=ALL` + non-root user | non-root uid 1001 on every image run |
| Container escape via kernel | seccomp extra denies (`mount`, `bpf`, `userfaultfd`, `clone3`, `unshare`) | `scripts/test-seccomp.sh` |
| CPU starvation of host | `--cpus=0.5` | observable via `docker stats` during runs |
| Infinite loop tying up the runner | watchdog `docker kill` after `timeoutMs` | `runner/tests/.../infinite loop in student code trips the watchdog` |
| stdout flood (log volume DoS) | `maxBuffer=1MB` → `kind=output_truncated` | covered by code path; not exercised end-to-end (would need a 1MB-emitting fixture) |

## Test runs (this session)

All three fixtures exercised via `./scripts/test-sandbox.sh`:

```
pass       -> kind=ok, verdict=passed (1/1)
fail       -> kind=ok, verdict=failed, expected/actual/hint propagated
malicious  -> kind=ok, verdict=passed (3/3 escape attempts contained:
              URLError, OSError, ptrace rv=-1)
```

Layered unit + integration suites:

```
scripts/test-seccomp.sh           ptrace blocked (rv=-1 errno=1), python OK
pytest tests/test_harness.py       13/13 PASS
runner/$ npm test                  8/8 PASS (2 unit + 6 integration)
```

## Known limitations and follow-ups

- macOS hosts run Docker Desktop which uses a Linux VM; behaviour matches
  Linux except for some `docker stats` precision and OOM kill latency.
- The seccomp profile is pinned to moby v27.3.1's default. When upgrading
  Docker, regenerate the profile (see `docs/sandbox-seccomp.md`) to pick up
  any new syscalls — otherwise newly-allowed syscalls might be unintentionally
  blocked, breaking student code.
- We rely on `--cpus=0.5` for soft scheduling; this is a CFS quota and not a
  hard isolation primitive. Multiple concurrent submissions still share the
  host CPU. The runner's `p-limit` (Faz 4.2) caps concurrency at 4.
