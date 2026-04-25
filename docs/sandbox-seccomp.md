# Sandbox Seccomp Profile

`infra/seccomp.json` — derived from moby's v27.3.1 default profile and
tightened per `01_BUILD_PLAN.md §2.2` and `00_MASTER_PROMPT.md §2.4`.

## How it's built

1. Start from moby's default seccomp (`defaultAction: SCMP_ACT_ERRNO`, explicit
   allow-list for the ~300 syscalls normal workloads need).
2. Strip the **extra-deny** syscalls out of every `SCMP_ACT_ALLOW` rule so
   they fall through to the default `ERRNO`.
3. Prepend an explicit `SCMP_ACT_ERRNO` rule naming all extra-denies — belt-
   and-suspenders and a stable anchor point for future audits.

Regeneration is a simple Python transform; see the commit that introduced
this file. If moby updates their default, re-run the transform against the
new upstream version.

## Extra-deny list and rationale

| Syscall        | Why blocked |
|----------------|-------------|
| `ptrace`       | Attach/read/write other processes' memory → break out of sandbox or inspect host state. |
| `unshare`      | Create new namespaces (user/net/pid/...) — foundation for container escape via user-namespace tricks. |
| `mount`        | Mount new filesystems inside container — bypass read-only bind mounts. |
| `umount` / `umount2` | Remove protective mounts (e.g. overlay read-only layer). |
| `keyctl`       | Manipulate kernel keyring — past CVEs allowed privilege escalation. |
| `bpf`          | Load eBPF programs — kernel bug surface, historically exploited for LPE. |
| `userfaultfd`  | User-space page fault handling — used in race-condition exploits (Dirty Pipe class). |
| `clone3`       | Richer `clone` variant — bypassed earlier seccomp filters that only looked at `clone`. |
| `reboot`       | Request kernel reboot (gated by `CAP_SYS_BOOT`, but deny at syscall level too). |

All of these are already gated by capability checks that we drop via
`--cap-drop=ALL` at run time (see Faz 2.4). Blocking them at the seccomp
layer is redundant-by-design: if any capability is ever granted back by
mistake, the syscall still fails with `EPERM`.

## Verification

`scripts/test-seccomp.sh` exercises the profile end-to-end:

- **Control**: run `ptrace(PTRACE_TRACEME)` without our profile → succeeds
  (`rv=0`). Proves the test is meaningful.
- **Test 1**: same call with our profile → `rv=-1 errno=1` (EPERM from
  `errnoRet: 1`). Proves the deny is active.
- **Test 2**: `python -c 'print(...)'` with our profile → prints normally.
  Proves we did not break the allow-list.

Run from the repo root after building `iau-sandbox:latest`:

```
./scripts/test-seccomp.sh
```
