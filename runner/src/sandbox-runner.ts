/**
 * Hardened `docker run` wrapper for executing student submissions.
 *
 * This is the single place where the security flags from
 * 00_MASTER_PROMPT.md §2.4 are applied. Upstream callers (the runner HTTP
 * service in Faz 4) MUST go through this function — they should never
 * spawn `docker run` directly.
 *
 * Timeout handling: Docker CLI is a client; killing the CLI does not stop
 * the container. We therefore pre-assign a container name and spawn a
 * detached watchdog that calls `docker kill` after the timeout. The
 * spawnSync `timeout` option exists only to recover from a stuck CLI
 * (dockerd is down, etc.).
 */

import { spawn, spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";

export interface SandboxRunInput {
  /** Host path to the directory containing `test_runner.py` — bind-mounted read-only at /workspace/tests. */
  readonly testsDir: string;
  /** Host path to the directory with the student's code — bind-mounted read-only at /workspace/code. */
  readonly codeDir: string;
  /** Host path to the seccomp profile JSON. */
  readonly seccompProfile: string;
  /** Docker image tag. Defaults to `iau-sandbox:latest`. */
  readonly image?: string;
  /** Wall-clock budget in milliseconds. Defaults to 10 000 (§2.4). */
  readonly timeoutMs?: number;
  /** Memory cap in MB. Defaults to 512 (§2.4). */
  readonly memoryMb?: number;
  /** CPU cap (fraction of one core). Defaults to 0.5 (§2.4). */
  readonly cpus?: number;
  /** Max processes. Defaults to 64 (§2.4). */
  readonly pidsLimit?: number;
  /** Path to the `docker` binary. Defaults to `docker` on PATH. */
  readonly dockerBin?: string;
}

export type SandboxRunOutcome =
  | { readonly kind: "ok"; readonly report: unknown; readonly elapsedMs: number }
  | { readonly kind: "timeout"; readonly elapsedMs: number }
  | { readonly kind: "crash"; readonly exitCode: number; readonly stderrTail: string; readonly elapsedMs: number }
  | { readonly kind: "invalid_json"; readonly stdoutTail: string; readonly stderrTail: string; readonly elapsedMs: number }
  | { readonly kind: "output_truncated"; readonly stdoutTail: string; readonly stderrTail: string; readonly elapsedMs: number };

const ONE_MB = 1_048_576;
const DEFAULTS = {
  image: "iau-sandbox:latest",
  timeoutMs: 10_000,
  memoryMb: 512,
  cpus: 0.5,
  pidsLimit: 64,
  dockerBin: "docker",
} as const;

/**
 * Build the list of `docker run` arguments. Exported for tests so we can
 * assert the exact command line without actually launching docker.
 */
export function buildDockerArgs(
  input: SandboxRunInput,
  containerName: string,
): readonly string[] {
  const image = input.image ?? DEFAULTS.image;
  const memoryMb = input.memoryMb ?? DEFAULTS.memoryMb;
  const cpus = input.cpus ?? DEFAULTS.cpus;
  const pidsLimit = input.pidsLimit ?? DEFAULTS.pidsLimit;

  return [
    "run",
    "--rm",
    "--name", containerName,
    // Isolation baseline per 00_MASTER_PROMPT.md §2.4.
    "--network=none",
    "--read-only",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--security-opt", `seccomp=${input.seccompProfile}`,
    // Resource caps — prevent fork bombs / memory hogs / CPU hogs.
    `--pids-limit=${pidsLimit}`,
    `--memory=${memoryMb}m`,
    // Leave swap disabled (equal to memory) to avoid silently exceeding the cap.
    `--memory-swap=${memoryMb}m`,
    `--cpus=${cpus}`,
    // Read-only rootfs requires a writable /tmp for pip caches, pytest, etc.
    // 64MB tmpfs is plenty for test execution.
    "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
    // Bind mounts: tests/ + code/ live under /workspace (harness expects this).
    "-v", `${input.testsDir}:/workspace/tests:ro`,
    "-v", `${input.codeDir}:/workspace/code:ro`,
    image,
  ];
}

/**
 * Run a submission inside a hardened sandbox container. Synchronous because
 * the caller (HTTP handler in Faz 4) runs inside a p-limit semaphore slot;
 * there's no concurrency benefit to making this async at the wrapper level.
 */
export function runSandbox(input: SandboxRunInput): SandboxRunOutcome {
  const dockerBin = input.dockerBin ?? DEFAULTS.dockerBin;
  const timeoutMs = input.timeoutMs ?? DEFAULTS.timeoutMs;
  const containerName = `iau-sub-${randomUUID()}`;
  const args = buildDockerArgs(input, containerName);

  // Watchdog: guaranteed kill of the container after timeoutMs, independent
  // of whether spawnSync managed to kill the CLI. Runs `docker kill` in a
  // detached shell; we reap it explicitly after spawnSync returns.
  const watchdogTimeoutSec = Math.max(1, Math.ceil(timeoutMs / 1000));
  const watchdog = spawn(
    "sh",
    [
      "-c",
      `sleep ${watchdogTimeoutSec} && ${dockerBin} kill ${containerName} >/dev/null 2>&1`,
    ],
    { detached: true, stdio: "ignore" },
  );
  watchdog.unref();

  const startedAt = Date.now();
  const result = spawnSync(dockerBin, args, {
    // Add a small grace window over the watchdog — lets docker kill propagate
    // before spawnSync force-terminates the client.
    timeout: timeoutMs + 3_000,
    killSignal: "SIGKILL",
    maxBuffer: ONE_MB,
    encoding: "utf8",
  });
  const elapsedMs = Date.now() - startedAt;

  // Best-effort watchdog cleanup. If it already fired, the kill is a no-op.
  try {
    if (watchdog.pid !== undefined) process.kill(-watchdog.pid, "SIGKILL");
  } catch {
    // expected when watchdog already exited
  }

  const stdout = typeof result.stdout === "string" ? result.stdout : "";
  const stderr = typeof result.stderr === "string" ? result.stderr : "";
  const stdoutTail = tail(stdout, ONE_MB);
  const stderrTail = tail(stderr, ONE_MB);

  // maxBuffer exceeded => Node sets error.code = 'ENOBUFS'.
  if (result.error && (result.error as NodeJS.ErrnoException).code === "ENOBUFS") {
    // Container's output blew past 1MB — refuse to parse it. The watchdog
    // has already (or will shortly) kill the container.
    return { kind: "output_truncated", stdoutTail, stderrTail, elapsedMs };
  }

  // Timeout path: watchdog killed the container or spawnSync's own timeout fired.
  // Container killed by SIGKILL from outside typically yields exit code 137.
  const timedOut =
    result.signal === "SIGKILL" ||
    (result.error as NodeJS.ErrnoException | undefined)?.code === "ETIMEDOUT" ||
    result.status === 137 ||
    elapsedMs >= timeoutMs;
  if (timedOut) {
    return { kind: "timeout", elapsedMs };
  }

  if (result.status === 0) {
    try {
      const report = JSON.parse(stdout);
      return { kind: "ok", report, elapsedMs };
    } catch {
      return { kind: "invalid_json", stdoutTail, stderrTail, elapsedMs };
    }
  }

  return {
    kind: "crash",
    exitCode: result.status ?? -1,
    stderrTail,
    elapsedMs,
  };
}

function tail(s: string, limit: number): string {
  return s.length <= limit ? s : s.slice(s.length - limit);
}
