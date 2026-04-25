/**
 * Per-submission orchestration: extract code ZIP, prepare workspace, invoke
 * the hardened sandbox runner, persist the report into Prisma.
 *
 * Faz 4.3 + 4.4 in one module — keeping them together makes the failure
 * paths (DB write before/after sandbox call) easier to reason about.
 */

import AdmZip from "adm-zip";
import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { prisma } from "./db.ts";
import { runSandbox } from "./sandbox-runner.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
// REPO_ROOT defaults to the runner package root, but is overridable via env
// for the docker-in-docker case: we need the *host* absolute path so that
// `docker run -v <path>:/workspace/...` resolves on the daemon's filesystem.
// Compose sets REPO_ROOT to the host repo root and mounts it at the same
// absolute path inside the runner container.
const REPO_ROOT = process.env.REPO_ROOT ?? resolve(__dirname, "..", "..");
const SECCOMP = join(REPO_ROOT, "infra", "seccomp.json");
const UNITS_DIR = join(REPO_ROOT, "content", "units");

export interface RunSubmissionInput {
  readonly submissionId: string;
  readonly userId: string;
  readonly unitSlug: string;
  readonly zipBuffer: Buffer;
  /** Override paths for testing. */
  readonly seccompProfile?: string;
  readonly unitsDir?: string;
}

export type RunSubmissionResult =
  | { readonly kind: "passed"; readonly verdict: "passed"; readonly elapsedMs: number }
  | { readonly kind: "failed"; readonly verdict: "failed"; readonly elapsedMs: number }
  | { readonly kind: "errored"; readonly reason: string; readonly elapsedMs: number };

/**
 * Drives a single submission end-to-end. Always settles to a final
 * Submission row state (PASSED / FAILED / ERRORED) — never leaves it stuck
 * in RUNNING, even if the sandbox crashes or the harness emits garbage.
 */
export async function runSubmission(
  input: RunSubmissionInput,
): Promise<RunSubmissionResult> {
  const unitsDir = input.unitsDir ?? UNITS_DIR;
  const seccomp = input.seccompProfile ?? SECCOMP;

  const startedAt = Date.now();
  const db = prisma();

  // Look up the unit (we need the order to find the unit folder; the slug
  // alone is ambiguous if folders disagree with the DB).
  const unit = await db.unit.findUnique({
    where: { slug: input.unitSlug },
    include: { testGroups: { include: { cases: true } } },
  });
  if (!unit) {
    return await failSubmission(
      db,
      input.submissionId,
      `unit not found: ${input.unitSlug}`,
      startedAt,
    );
  }

  // Mark RUNNING before the heavy lifting. The partial unique index on
  // Submission(userId, unitId) WHERE status='RUNNING' guarantees that two
  // requests cannot be in this state simultaneously for the same pair.
  await db.submission.update({
    where: { id: input.submissionId },
    data: { status: "RUNNING" },
  });

  const orderStr = unit.order.toString().padStart(2, "0");
  const unitFolder = join(unitsDir, `unit-${orderStr}-${input.unitSlug}`);
  const testsDir = join(unitFolder, "tests");
  if (!existsSync(testsDir)) {
    return await failSubmission(
      db,
      input.submissionId,
      `tests/ folder missing for unit ${input.unitSlug} at ${testsDir}`,
      startedAt,
    );
  }

  const tmpRoot = mkdtempSync(join(tmpdir(), `iau-sub-${input.submissionId}-`));
  const codeDir = join(tmpRoot, "code");
  mkdirSync(codeDir, { recursive: true });
  try {
    // Extract submission ZIP into codeDir. AdmZip will reject path traversal
    // by default in extractAllTo. We additionally cap entry count.
    const zip = new AdmZip(input.zipBuffer);
    const entries = zip.getEntries();
    if (entries.length > 200) {
      return await failSubmission(
        db,
        input.submissionId,
        `submission has too many entries (${entries.length} > 200)`,
        startedAt,
      );
    }
    zip.extractAllTo(codeDir, /* overwrite */ true);

    const outcome = runSandbox({
      testsDir,
      codeDir,
      seccompProfile: seccomp,
    });

    const elapsedMs = Date.now() - startedAt;
    return await persistOutcome(db, input.submissionId, unit, outcome, elapsedMs);
  } catch (e) {
    return await failSubmission(
      db,
      input.submissionId,
      `runner crashed: ${(e as Error).message}`,
      startedAt,
    );
  } finally {
    rmSync(tmpRoot, { recursive: true, force: true });
  }
}

// ---------------------------------------------------------------------------
// DB write helpers
// ---------------------------------------------------------------------------

interface UnitWithTests {
  readonly id: string;
  readonly testGroups: readonly {
    readonly id: string;
    readonly name: string;
    readonly cases: readonly { readonly id: string; readonly extId: string }[];
  }[];
}

interface HarnessReport {
  readonly summary: { readonly verdict: string; readonly runtime_ms?: number };
  readonly groups: readonly {
    readonly name: string;
    readonly tests: readonly {
      readonly id: string;
      readonly status: string;
      readonly detail?: string;
      readonly runtime_ms?: number;
    }[];
  }[];
}

async function persistOutcome(
  db: ReturnType<typeof prisma>,
  submissionId: string,
  unit: UnitWithTests,
  outcome: ReturnType<typeof runSandbox>,
  elapsedMs: number,
): Promise<RunSubmissionResult> {
  // Sandbox-level failures. Always emit a final row state.
  if (outcome.kind === "timeout") {
    await db.submission.update({
      where: { id: submissionId },
      data: {
        status: "ERRORED",
        report: { error: "sandbox timeout", elapsedMs: outcome.elapsedMs },
      },
    });
    return { kind: "errored", reason: "timeout", elapsedMs };
  }
  if (outcome.kind === "crash") {
    await db.submission.update({
      where: { id: submissionId },
      data: {
        status: "ERRORED",
        report: { error: "sandbox crash", exitCode: outcome.exitCode, stderr: outcome.stderrTail },
      },
    });
    return { kind: "errored", reason: "crash", elapsedMs };
  }
  if (outcome.kind === "invalid_json" || outcome.kind === "output_truncated") {
    await db.submission.update({
      where: { id: submissionId },
      data: {
        status: "ERRORED",
        report: { error: outcome.kind, stdout: outcome.stdoutTail, stderr: outcome.stderrTail },
      },
    });
    return { kind: "errored", reason: outcome.kind, elapsedMs };
  }

  // outcome.kind === "ok" — a parsed harness report.
  const report = outcome.report as HarnessReport;
  const verdict = report.summary?.verdict;
  const finalStatus = verdict === "passed" ? "PASSED" : "FAILED";

  await db.$transaction(async (tx) => {
    // Persist top-level submission state + raw JSON for debugging / display.
    await tx.submission.update({
      where: { id: submissionId },
      data: {
        status: finalStatus,
        report: report as object,
      },
    });

    // Wipe and re-write the per-test rows (we never care about prior partial
    // results for the same submission — there shouldn't be any, but the
    // semantics are clearer this way).
    await tx.submissionTestResult.deleteMany({ where: { submissionId } });

    for (const g of report.groups) {
      const dbGroup = unit.testGroups.find((tg) => tg.name === g.name);
      if (!dbGroup) continue; // harness emitted an unexpected group; skip silently
      for (const t of g.tests) {
        // Lazy-upsert TestCase by (testGroupId, extId).
        const dbCase = await tx.testCase.upsert({
          where: { testGroupId_extId: { testGroupId: dbGroup.id, extId: t.id } },
          create: {
            testGroupId: dbGroup.id,
            extId: t.id,
            name: t.id,
          },
          update: {},
        });
        await tx.submissionTestResult.create({
          data: {
            submissionId,
            testCaseId: dbCase.id,
            status: mapStatus(t.status),
            detail: t.detail ?? null,
            runtimeMs: t.runtime_ms ?? null,
          },
        });
      }
    }
  });

  // Unlock the next unit on a passing submission.
  if (verdict === "passed") {
    const submission = await db.submission.findUniqueOrThrow({
      where: { id: submissionId },
      select: { userId: true, unitId: true },
    });
    await db.unitProgress.upsert({
      where: { userId_unitId: { userId: submission.userId, unitId: submission.unitId } },
      create: {
        userId: submission.userId,
        unitId: submission.unitId,
        status: "COMPLETED",
        completedAt: new Date(),
      },
      update: { status: "COMPLETED", completedAt: new Date() },
    });
    const next = await db.unit.findFirst({
      where: { order: { gt: (await db.unit.findUniqueOrThrow({ where: { id: submission.unitId } })).order } },
      orderBy: { order: "asc" },
    });
    if (next) {
      await db.unitProgress.upsert({
        where: { userId_unitId: { userId: submission.userId, unitId: next.id } },
        create: { userId: submission.userId, unitId: next.id, status: "IN_PROGRESS" },
        update: {
          status: { set: "IN_PROGRESS" },
        },
      });
    }
  }

  return verdict === "passed"
    ? { kind: "passed", verdict: "passed", elapsedMs }
    : { kind: "failed", verdict: "failed", elapsedMs };
}

function mapStatus(s: string): "PASSED" | "FAILED" | "ERRORED" | "TIMEOUT" {
  switch (s) {
    case "passed":
      return "PASSED";
    case "failed":
      return "FAILED";
    case "errored":
      return "ERRORED";
    case "timeout":
      return "TIMEOUT";
    default:
      return "ERRORED";
  }
}

async function failSubmission(
  db: ReturnType<typeof prisma>,
  submissionId: string,
  reason: string,
  startedAt: number,
): Promise<RunSubmissionResult> {
  await db.submission.update({
    where: { id: submissionId },
    data: {
      status: "ERRORED",
      report: { error: reason },
    },
  });
  return { kind: "errored", reason, elapsedMs: Date.now() - startedAt };
}

export function hashZip(buf: Buffer): string {
  return createHash("sha256").update(buf).digest("hex");
}
