/**
 * Unit tests for the ingest pipeline. The reference-solution sandbox check
 * is skipped here (`skipReferenceCheck: true`) so the suite does not need
 * docker; the runner CLI itself is covered by runner/tests/.
 */

import AdmZip from "adm-zip";
import { strict as assert } from "node:assert";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, describe, test } from "node:test";

import {
  assertRequiredFiles,
  assertUnitYamlMatches,
  FILENAME_RE,
  ingestAll,
  ingestOne,
  parseFilename,
  REQUIRED_FILES,
  type UnitYaml,
} from "./ingest-content.ts";

interface Workspace {
  root: string;
  inbox: string;
  units: string;
  pdfs: string;
}

function mkWorkspace(): Workspace {
  const root = mkdtempSync(join(tmpdir(), "iau-ingest-test-"));
  const inbox = join(root, "inbox");
  const units = join(root, "units");
  const pdfs = join(root, "pdfs");
  for (const d of [inbox, units, pdfs]) mkdirSync(d, { recursive: true });
  return { root, inbox, units, pdfs };
}

function defaultUnitYaml(slug = "welcome", order = 0): UnitYaml {
  return {
    order,
    slug,
    title: "Welcome",
    description: "Intro unit",
    tags: ["intro"],
    duration_minutes: 60,
    published: true,
    test_groups: [{ name: "Hello world", weight: 1, order: 1 }],
  };
}

function buildUnitZip(
  inbox: string,
  zipName: string,
  unitYaml: UnitYaml,
  overrides: { omit?: readonly string[] } = {},
): string {
  const zip = new AdmZip();
  const omit = new Set(overrides.omit ?? []);
  if (!omit.has("unit.yaml")) {
    zip.addFile(
      "unit.yaml",
      Buffer.from(
        `order: ${unitYaml.order}\nslug: ${unitYaml.slug}\ntitle: ${unitYaml.title}\n` +
          `description: ${unitYaml.description}\npublished: ${unitYaml.published}\n` +
          `test_groups:\n  - name: Hello world\n    weight: 1\n    order: 1\n`,
      ),
    );
  }
  if (!omit.has("education.pdf")) {
    zip.addFile("education.pdf", Buffer.from("%PDF-1.4 fake"));
  }
  if (!omit.has("projects.md")) {
    zip.addFile("projects.md", Buffer.from("# Projects\nDo the thing.\n"));
  }
  if (!omit.has("tests/test_runner.py")) {
    zip.addFile(
      "tests/test_runner.py",
      Buffer.from("from harness_api import TestGroup\ndef run_tests():\n    return [TestGroup(name='g')]\n"),
    );
  }
  if (!omit.has("reference/pass_final.zip")) {
    const inner = new AdmZip();
    inner.addFile("solution.py", Buffer.from("print('ok')\n"));
    zip.addFile("reference/pass_final.zip", inner.toBuffer());
  }
  const path = join(inbox, zipName);
  zip.writeZip(path);
  return path;
}

// ---------------------------------------------------------------------------
// Pure validators
// ---------------------------------------------------------------------------

describe("parseFilename", () => {
  test("accepts well-formed names", () => {
    assert.deepEqual(parseFilename("unit-00-welcome.zip"), {
      order: 0,
      slug: "welcome",
    });
    assert.deepEqual(parseFilename("unit-07-rag-pipeline.zip"), {
      order: 7,
      slug: "rag-pipeline",
    });
  });

  test("rejects bad shapes", () => {
    assert.throws(() => parseFilename("unit-7-rag.zip"));      // single digit
    assert.throws(() => parseFilename("unit-01-RAG.zip"));     // upper
    assert.throws(() => parseFilename("unit-01.zip"));         // no slug
    assert.throws(() => parseFilename("unit-01-x.tar.gz"));    // wrong ext
    assert.throws(() => parseFilename("ünite-01-x.zip"));      // non-ASCII
  });
});

describe("assertRequiredFiles", () => {
  test("detects each missing required file individually", () => {
    for (const omit of REQUIRED_FILES) {
      const ws = mkWorkspace();
      try {
        // create everything except `omit`
        for (const f of REQUIRED_FILES) {
          if (f === omit) continue;
          const p = join(ws.root, f);
          mkdirSync(join(ws.root, f.includes("/") ? f.split("/")[0]! : ""), {
            recursive: true,
          });
          writeFileSync(p, "x");
        }
        assert.throws(() => assertRequiredFiles(ws.root), /missing required file/);
      } finally {
        rmSync(ws.root, { recursive: true, force: true });
      }
    }
  });
});

describe("assertUnitYamlMatches", () => {
  test("accepts a valid yaml", () => {
    assertUnitYamlMatches(defaultUnitYaml("welcome", 0), "welcome", 0);
  });
  test("flags slug mismatch", () => {
    assert.throws(
      () => assertUnitYamlMatches(defaultUnitYaml("rag", 0), "welcome", 0),
      /slug/,
    );
  });
  test("flags order mismatch", () => {
    assert.throws(
      () => assertUnitYamlMatches(defaultUnitYaml("welcome", 5), "welcome", 0),
      /order/,
    );
  });
  test("flags missing title / description", () => {
    const bad = { ...defaultUnitYaml(), title: "" } as UnitYaml;
    assert.throws(() => assertUnitYamlMatches(bad, "welcome", 0), /title/);
  });
});

// ---------------------------------------------------------------------------
// End-to-end on a tmp workspace (no docker, no DB)
// ---------------------------------------------------------------------------

describe("ingestOne (dry-run, no sandbox)", () => {
  const created: Workspace[] = [];
  const track = (w: Workspace): Workspace => {
    created.push(w);
    return w;
  };
  after(() => {
    for (const w of created) rmSync(w.root, { recursive: true, force: true });
  });

  test("happy path returns dry-run-ok and leaves zip in inbox", async () => {
    const ws = track(mkWorkspace());
    const zipPath = buildUnitZip(
      ws.inbox,
      "unit-00-welcome.zip",
      defaultUnitYaml(),
    );
    const out = await ingestOne("unit-00-welcome.zip", {
      dryRun: true,
      inboxDir: ws.inbox,
      unitsDir: ws.units,
      pdfsOutDir: ws.pdfs,
      skipReferenceCheck: true,
    });
    assert.equal(out.kind, "dry-run-ok");
    if (out.kind !== "dry-run-ok") return;
    assert.equal(out.slug, "welcome");
    assert.equal(out.order, 0);
    assert.ok(existsSync(zipPath), "zip must remain in inbox during dry-run");
  });

  test("bad filename is rejected", async () => {
    const ws = track(mkWorkspace());
    buildUnitZip(ws.inbox, "unit-1-x.zip", defaultUnitYaml());
    await assert.rejects(
      ingestOne("unit-1-x.zip", { dryRun: true, inboxDir: ws.inbox, skipReferenceCheck: true }),
      /filename does not match/,
    );
  });

  test("missing tests/test_runner.py is rejected", async () => {
    const ws = track(mkWorkspace());
    buildUnitZip(ws.inbox, "unit-00-welcome.zip", defaultUnitYaml(), {
      omit: ["tests/test_runner.py"],
    });
    await assert.rejects(
      ingestOne("unit-00-welcome.zip", {
        dryRun: true,
        inboxDir: ws.inbox,
        unitsDir: ws.units,
        pdfsOutDir: ws.pdfs,
        skipReferenceCheck: true,
      }),
      /missing required file: tests\/test_runner.py/,
    );
  });

  test("yaml slug/order disagreement with filename rejected", async () => {
    const ws = track(mkWorkspace());
    // filename says order=00, slug=welcome; yaml says slug=other
    buildUnitZip(
      ws.inbox,
      "unit-00-welcome.zip",
      defaultUnitYaml("other", 0),
    );
    await assert.rejects(
      ingestOne("unit-00-welcome.zip", {
        dryRun: true,
        inboxDir: ws.inbox,
        unitsDir: ws.units,
        pdfsOutDir: ws.pdfs,
        skipReferenceCheck: true,
      }),
      /slug/,
    );
  });
});

// ---------------------------------------------------------------------------
// ingestAll: directory-level orchestration
// ---------------------------------------------------------------------------

describe("ingestAll (dry-run, no sandbox)", () => {
  test("processes all valid zips and writes errors.log for invalid ones", async () => {
    const ws = mkWorkspace();
    try {
      buildUnitZip(ws.inbox, "unit-00-welcome.zip", defaultUnitYaml("welcome", 0));
      buildUnitZip(ws.inbox, "unit-01-rag.zip", defaultUnitYaml("rag", 1));
      buildUnitZip(ws.inbox, "unit-02-bad.zip", defaultUnitYaml("bad", 2), {
        omit: ["unit.yaml"],
      });

      const outcomes = await ingestAll({
        dryRun: true,
        inboxDir: ws.inbox,
        unitsDir: ws.units,
        pdfsOutDir: ws.pdfs,
        skipReferenceCheck: true,
      });

      const kinds = outcomes.map((o) => o.kind).sort();
      assert.deepEqual(kinds, ["dry-run-ok", "dry-run-ok", "rejected"]);

      const logPath = join(ws.inbox, "errors", "unit-02-bad.zip.log");
      assert.ok(existsSync(logPath), "expected error log for the bad zip");
      const log = readFileSync(logPath, "utf8");
      assert.match(log, /missing required file/);
    } finally {
      rmSync(ws.root, { recursive: true, force: true });
    }
  });
});

// FILENAME_RE sanity (cheap)
describe("FILENAME_RE", () => {
  test("matches expected forms", () => {
    assert.ok(FILENAME_RE.test("unit-00-x.zip"));
    assert.ok(FILENAME_RE.test("unit-99-some-long-slug.zip"));
    assert.ok(!FILENAME_RE.test("unit-100-x.zip"));
    assert.ok(!FILENAME_RE.test("UNIT-01-X.ZIP"));
  });
});
