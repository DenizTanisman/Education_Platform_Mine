/**
 * Integration tests for runSandbox.
 *
 * These spawn real containers from iau-sandbox:latest. Run:
 *   docker build -t iau-sandbox:latest -f infra/sandbox.Dockerfile .
 * before executing the suite.
 *
 * Each test writes a synthetic tests/test_runner.py + code/solution.py pair
 * into a tmp workspace, invokes runSandbox, and asserts on the outcome kind
 * and — where relevant — on the embedded harness report.
 */

import { strict as assert } from "node:assert";
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { after, before, describe, test } from "node:test";

import { buildDockerArgs, runSandbox, type SandboxRunOutcome } from "../src/sandbox-runner.ts";

const REPO_ROOT = resolve(import.meta.dirname, "..", "..");
const SECCOMP = join(REPO_ROOT, "infra", "seccomp.json");

interface Scratch {
  readonly root: string;
  readonly testsDir: string;
  readonly codeDir: string;
}

function makeScratch(): Scratch {
  const root = mkdtempSync(join(tmpdir(), "iau-runner-"));
  const testsDir = join(root, "tests");
  const codeDir = join(root, "code");
  mkdirSync(testsDir);
  mkdirSync(codeDir);
  return { root, testsDir, codeDir };
}

function writeRunner(s: Scratch, src: string): void {
  writeFileSync(join(s.testsDir, "test_runner.py"), src);
}

function writeSolution(s: Scratch, src: string): void {
  writeFileSync(join(s.codeDir, "solution.py"), src);
}

function cleanup(s: Scratch): void {
  rmSync(s.root, { recursive: true, force: true });
}

// ---------------------------------------------------------------------------
// Unit test: argument construction (no docker needed)
// ---------------------------------------------------------------------------
describe("buildDockerArgs", () => {
  test("emits all §2.4 security flags in the expected order", () => {
    const args = buildDockerArgs(
      {
        testsDir: "/t",
        codeDir: "/c",
        seccompProfile: "/profile.json",
      },
      "iau-sub-abc",
    );
    assert.ok(args.includes("--network=none"));
    assert.ok(args.includes("--read-only"));
    assert.ok(args.includes("--cap-drop=ALL"));
    assert.ok(args.includes("--security-opt=no-new-privileges"));
    assert.ok(args.includes("--pids-limit=64"));
    assert.ok(args.includes("--memory=512m"));
    assert.ok(args.includes("--memory-swap=512m"));
    assert.ok(args.includes("--cpus=0.5"));
    // seccomp is passed as a two-arg pair
    const seccompIdx = args.indexOf("--security-opt");
    assert.ok(seccompIdx >= 0);
    assert.equal(args[seccompIdx + 1], "seccomp=/profile.json");
    // bind mounts present as two-arg pairs
    assert.ok(args.some((a, i) => a === "-v" && args[i + 1] === "/t:/workspace/tests:ro"));
    assert.ok(args.some((a, i) => a === "-v" && args[i + 1] === "/c:/workspace/code:ro"));
    // named container
    assert.ok(args.includes("iau-sub-abc"));
  });

  test("honours overrides for resource caps and image tag", () => {
    const args = buildDockerArgs(
      {
        testsDir: "/t",
        codeDir: "/c",
        seccompProfile: "/p.json",
        image: "custom:tag",
        memoryMb: 256,
        cpus: 0.25,
        pidsLimit: 32,
      },
      "iau-sub-x",
    );
    assert.ok(args.includes("--memory=256m"));
    assert.ok(args.includes("--memory-swap=256m"));
    assert.ok(args.includes("--cpus=0.25"));
    assert.ok(args.includes("--pids-limit=32"));
    assert.equal(args[args.length - 1], "custom:tag");
  });
});

// ---------------------------------------------------------------------------
// Integration: spawns real containers. Each test is self-cleaning.
// ---------------------------------------------------------------------------
describe("runSandbox integration", () => {
  const scratches: Scratch[] = [];
  const track = (s: Scratch): Scratch => {
    scratches.push(s);
    return s;
  };
  after(() => {
    for (const s of scratches) cleanup(s);
  });

  // Basic happy path
  test("passing submission yields kind=ok with verdict=passed", () => {
    const s = track(makeScratch());
    writeSolution(s, "def ping(): return 'pong'\n");
    writeRunner(
      s,
      [
        "from harness_api import TestGroup, TestResult",
        "def run_tests():",
        "    from solution import ping",
        "    g = TestGroup(name='g')",
        "    g.add(TestResult(id='t', status='passed' if ping() == 'pong' else 'failed'))",
        "    return [g]",
      ].join("\n"),
    );
    const out = runSandbox({
      testsDir: s.testsDir,
      codeDir: s.codeDir,
      seccompProfile: SECCOMP,
    });
    assert.equal(out.kind, "ok");
    if (out.kind !== "ok") return;
    const report = out.report as { summary: { verdict: string } };
    assert.equal(report.summary.verdict, "passed");
  });

  // Timeout — student code loops forever
  test("infinite loop in student code trips the watchdog -> kind=timeout", () => {
    const s = track(makeScratch());
    writeSolution(s, "def spin():\n    while True: pass\n");
    writeRunner(
      s,
      [
        "from harness_api import TestGroup",
        "def run_tests():",
        "    from solution import spin",
        "    spin()",
        "    return [TestGroup(name='unreached')]",
      ].join("\n"),
    );
    const out = runSandbox({
      testsDir: s.testsDir,
      codeDir: s.codeDir,
      seccompProfile: SECCOMP,
      timeoutMs: 2_000,
    });
    assert.equal(out.kind, "timeout", `expected timeout, got ${out.kind}`);
  });

  // Network deny — urlopen should raise gaierror (no DNS under --network=none)
  test("network access raises gaierror (verified via harness errored status)", () => {
    const s = track(makeScratch());
    writeSolution(
      s,
      [
        "import urllib.request",
        "def fetch():",
        "    urllib.request.urlopen('http://example.com', timeout=1)",
      ].join("\n"),
    );
    writeRunner(
      s,
      [
        "from harness_api import TestGroup, TestResult",
        "def run_tests():",
        "    g = TestGroup(name='net')",
        "    try:",
        "        from solution import fetch",
        "        fetch()",
        "        g.add(TestResult(id='t', status='passed'))",
        "    except Exception as e:",
        "        g.add(TestResult(id='t', status='errored', detail=type(e).__name__ + ':' + str(e)))",
        "    return [g]",
      ].join("\n"),
    );
    const out = runSandbox({
      testsDir: s.testsDir,
      codeDir: s.codeDir,
      seccompProfile: SECCOMP,
      timeoutMs: 10_000,
    });
    assert.equal(out.kind, "ok");
    if (out.kind !== "ok") return;
    const report = out.report as {
      summary: { errored: number };
      groups: { tests: { status: string; detail?: string }[] }[];
    };
    assert.equal(report.summary.errored, 1);
    const detail = report.groups[0]!.tests[0]!.detail ?? "";
    assert.match(
      detail,
      /gaierror|URLError|Network is unreachable|Name or service not known/,
      `expected network error, got: ${detail}`,
    );
  });

  // Read-only root — writing to /etc must fail
  test("write to /etc/ fails under --read-only", () => {
    const s = track(makeScratch());
    writeSolution(
      s,
      [
        "def leak():",
        "    with open('/etc/iau-evil', 'w') as f:",
        "        f.write('bad')",
      ].join("\n"),
    );
    writeRunner(
      s,
      [
        "from harness_api import TestGroup, TestResult",
        "def run_tests():",
        "    g = TestGroup(name='fs')",
        "    try:",
        "        from solution import leak",
        "        leak()",
        "        g.add(TestResult(id='t', status='passed'))",
        "    except Exception as e:",
        "        g.add(TestResult(id='t', status='errored', detail=type(e).__name__))",
        "    return [g]",
      ].join("\n"),
    );
    const out = runSandbox({
      testsDir: s.testsDir,
      codeDir: s.codeDir,
      seccompProfile: SECCOMP,
    });
    assert.equal(out.kind, "ok");
    if (out.kind !== "ok") return;
    const report = out.report as {
      groups: { tests: { detail?: string }[] }[];
    };
    const detail = report.groups[0]!.tests[0]!.detail ?? "";
    assert.match(detail, /OSError|PermissionError|ReadOnlyFileSystem/, `got: ${detail}`);
  });

  // pids-limit contains fork bombs
  test("fork-heavy student code is bounded by --pids-limit (container finishes, host unaffected)", () => {
    const s = track(makeScratch());
    writeSolution(
      s,
      [
        "import os",
        "def bomb():",
        "    for _ in range(500):",
        "        pid = os.fork()",
        "        if pid == 0:",
        "            # child: sleep to keep the slot occupied",
        "            import time; time.sleep(5); os._exit(0)",
      ].join("\n"),
    );
    writeRunner(
      s,
      [
        "from harness_api import TestGroup, TestResult",
        "def run_tests():",
        "    g = TestGroup(name='forks')",
        "    try:",
        "        from solution import bomb",
        "        bomb()",
        "        g.add(TestResult(id='t', status='passed'))",
        "    except Exception as e:",
        "        g.add(TestResult(id='t', status='errored', detail=type(e).__name__))",
        "    return [g]",
      ].join("\n"),
    );
    const out = runSandbox({
      testsDir: s.testsDir,
      codeDir: s.codeDir,
      seccompProfile: SECCOMP,
      timeoutMs: 6_000,
      pidsLimit: 16, // tighter than default for a faster/cleaner test
    });
    // Two valid outcomes: (a) errored status from BlockingIOError as fork hits
    // the limit, (b) timeout if children keep the container alive until the
    // watchdog fires. Both prove the bomb is contained.
    assert.ok(
      out.kind === "ok" || out.kind === "timeout",
      `unexpected kind ${out.kind}`,
    );
    if (out.kind === "ok") {
      const report = out.report as {
        groups: { tests: { status: string; detail?: string }[] }[];
      };
      assert.equal(report.groups[0]!.tests[0]!.status, "errored");
    }
  });

  // Fail propagation — a normally-failing submission keeps JSON structure intact
  test("failing test propagates through as ok/failed verdict", () => {
    const s = track(makeScratch());
    writeSolution(s, "def ping(): return 'wrong'\n");
    writeRunner(
      s,
      [
        "from harness_api import TestGroup, TestResult",
        "def run_tests():",
        "    from solution import ping",
        "    g = TestGroup(name='g')",
        "    g.add(TestResult(id='t', status='failed', expected=\"'pong'\", actual=repr(ping())))",
        "    return [g]",
      ].join("\n"),
    );
    const out = runSandbox({
      testsDir: s.testsDir,
      codeDir: s.codeDir,
      seccompProfile: SECCOMP,
    });
    assert.equal(out.kind, "ok");
    if (out.kind !== "ok") return;
    const report = out.report as { summary: { verdict: string; failed: number } };
    assert.equal(report.summary.verdict, "failed");
    assert.equal(report.summary.failed, 1);
  });
});
