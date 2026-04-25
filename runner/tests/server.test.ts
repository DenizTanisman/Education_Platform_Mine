/**
 * HTTP-level tests for the runner service. We exercise auth, queue full,
 * input validation, and the full happy path (real sandbox + real Prisma
 * write) using fixture units.
 *
 * The end-to-end test seeds a temp Unit + User in the dev database, runs a
 * passing submission through, and verifies Submission.status, the
 * SubmissionTestResult rows, and the unit-progress upsert. Cleanup deletes
 * everything we created so the suite is idempotent.
 */

import AdmZip from "adm-zip";
import { strict as assert } from "node:assert";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { createApp, MAX_ZIP_BYTES } from "../src/server.ts";
import { prisma, disconnect } from "../src/db.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..", "..");
const SECCOMP = join(REPO_ROOT, "infra", "seccomp.json");

const SECRET = "test-secret-12345";

interface Listener {
  url: string;
  close: () => Promise<void>;
}

async function listen(app: ReturnType<typeof createApp>): Promise<Listener> {
  const server = app.listen(0);
  await new Promise<void>((r) => server.once("listening", () => r()));
  const addr = server.address();
  if (!addr || typeof addr === "string") throw new Error("no port");
  const url = `http://127.0.0.1:${addr.port}`;
  const close = (): Promise<void> =>
    new Promise<void>((resolve, reject) =>
      server.close((err) => (err ? reject(err) : resolve())),
    );
  return { url, close };
}

function buildSubmissionZip(): Buffer {
  const zip = new AdmZip();
  zip.addFile("solution.py", Buffer.from('def greet(name): return f"Hello, {name}!"\n'));
  return zip.toBuffer();
}

function setupUnitOnDisk(unitsDir: string, slug: string, order: number): void {
  const orderStr = order.toString().padStart(2, "0");
  const unitDir = join(unitsDir, `unit-${orderStr}-${slug}`);
  const testsDir = join(unitDir, "tests");
  mkdirSync(testsDir, { recursive: true });
  writeFileSync(
    join(testsDir, "test_runner.py"),
    [
      "from harness_api import TestGroup, TestResult",
      "def run_tests():",
      "    g = TestGroup(name='greeting')",
      "    from solution import greet",
      "    actual = greet('Deniz')",
      "    g.add(TestResult(",
      "        id='test_greet_basic',",
      "        status='passed' if actual == 'Hello, Deniz!' else 'failed',",
      "        actual=repr(actual),",
      "    ))",
      "    return [g]",
      "",
    ].join("\n"),
  );
}

// ---------------------------------------------------------------------------
// Pure HTTP behaviour (no DB, no docker)
// ---------------------------------------------------------------------------

describe("server / health + auth", () => {
  test("/healthz returns ok and queue stats", async () => {
    const app = createApp({ sharedSecret: SECRET, seccompProfile: SECCOMP });
    const l = await listen(app);
    try {
      const r = await fetch(`${l.url}/healthz`);
      assert.equal(r.status, 200);
      const body = (await r.json()) as Record<string, unknown>;
      assert.equal(body.ok, true);
      assert.equal(typeof body.active, "number");
    } finally {
      await l.close();
    }
  });

  test("/run rejects missing secret", async () => {
    const app = createApp({ sharedSecret: SECRET, seccompProfile: SECCOMP });
    const l = await listen(app);
    try {
      const r = await fetch(`${l.url}/run`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({}),
      });
      assert.equal(r.status, 401);
    } finally {
      await l.close();
    }
  });

  test("/run rejects malformed input even with valid secret", async () => {
    const app = createApp({ sharedSecret: SECRET, seccompProfile: SECCOMP });
    const l = await listen(app);
    try {
      const r = await fetch(`${l.url}/run`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-runner-secret": SECRET,
        },
        body: JSON.stringify({ submissionId: "x" }),
      });
      assert.equal(r.status, 400);
    } finally {
      await l.close();
    }
  });
});

// ---------------------------------------------------------------------------
// Full happy path: real sandbox + real Prisma write
// ---------------------------------------------------------------------------

describe("server / end-to-end happy path", () => {
  const unitsDir = mkdtempSync(join(tmpdir(), "iau-units-"));
  const slug = `e2e-${Math.random().toString(36).slice(2, 8)}`;
  // Same value used for the on-disk folder name AND the DB row's `order`,
  // so runner-core's lookup `unit-<pad2(order)>-<slug>/` resolves correctly.
  // 9_000_000+ keeps us out of the way of real ingested units (orders 0..99).
  const unitOrder = 9_000_000 + Math.floor(Math.random() * 1000);
  let userId = "";
  let unitId = "";
  let submissionId = "";

  before(async () => {
    setupUnitOnDisk(unitsDir, slug, unitOrder);
    const db = prisma();
    const user = await db.user.create({
      data: { email: `${slug}@test.example`, passwordHash: "x", role: "STUDENT" },
    });
    userId = user.id;
    const unit = await db.unit.create({
      data: {
        slug,
        order: unitOrder,
        title: "E2E",
        description: "test",
      },
    });
    unitId = unit.id;
    await db.testGroup.create({
      data: { unitId: unit.id, name: "greeting", order: 1, weight: 1 },
    });
    const sub = await db.submission.create({
      data: { userId: user.id, unitId: unit.id, status: "QUEUED", zipHash: "x" },
    });
    submissionId = sub.id;
  });

  after(async () => {
    if (existsSync(unitsDir)) rmSync(unitsDir, { recursive: true, force: true });
    const db = prisma();
    await db.submissionTestResult.deleteMany({ where: { submission: { userId } } });
    await db.submission.deleteMany({ where: { userId } });
    await db.unitProgress.deleteMany({ where: { userId } });
    await db.testCase.deleteMany({ where: { testGroup: { unitId } } });
    await db.testGroup.deleteMany({ where: { unitId } });
    await db.unit.deleteMany({ where: { id: unitId } });
    await db.user.deleteMany({ where: { id: userId } });
    await disconnect();
  });

  test("passing submission moves status to PASSED and writes per-test rows", async () => {
    const app = createApp({
      sharedSecret: SECRET,
      seccompProfile: SECCOMP,
      unitsDir,
    });
    const l = await listen(app);
    try {
      const zip = buildSubmissionZip();
      const r = await fetch(`${l.url}/run`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-runner-secret": SECRET,
        },
        body: JSON.stringify({
          submissionId,
          userId,
          unitSlug: slug,
          zipBase64: zip.toString("base64"),
        }),
      });
      assert.equal(r.status, 200);
      const body = (await r.json()) as { kind: string; verdict?: string };
      assert.equal(body.kind, "passed", `expected passed, got ${JSON.stringify(body)}`);

      const db = prisma();
      const sub = await db.submission.findUniqueOrThrow({
        where: { id: submissionId },
        include: { results: true },
      });
      assert.equal(sub.status, "PASSED");
      assert.equal(sub.results.length, 1);
      assert.equal(sub.results[0]!.status, "PASSED");

      const progress = await db.unitProgress.findUniqueOrThrow({
        where: { userId_unitId: { userId, unitId } },
      });
      assert.equal(progress.status, "COMPLETED");
    } finally {
      await l.close();
    }
  });
});
