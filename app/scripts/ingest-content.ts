/**
 * Ingest content packages from `content/inbox/*.zip` per
 * 02_CONTENT_CONTRACT.md.
 *
 * Pipeline per ZIP:
 *   1. Validate filename matches `^unit-\d{2}-[a-z0-9-]+\.zip$`.
 *   2. Extract to a tmp dir; verify required files present (unit.yaml,
 *      education.pdf, projects.md, tests/test_runner.py, reference/pass_final.zip).
 *   3. Parse unit.yaml; cross-check slug + order with filename.
 *   4. Run reference/pass_final.zip through the hardened sandbox runner;
 *      every test must pass — otherwise the ZIP is rejected (a broken
 *      reference solution is a content bug, not a student bug).
 *   5. Upsert Unit + child rows (Video, Project, TestGroup) via Prisma.
 *      TestCase rows are created lazily on first real submission.
 *   6. Move accepted ZIPs to `content/inbox/processed/`, copy education.pdf
 *      to `app/public/pdfs/<slug>.pdf`, and lay the unit folder out under
 *      `content/units/unit-NN-slug/`.
 *
 * Failures are written to `content/inbox/errors/<zip>.log`; the original
 * ZIP stays in `content/inbox/` so Deniz can fix and re-run.
 *
 * `--dry-run` performs steps 1-4 but skips DB / filesystem mutations.
 */

import AdmZip from "adm-zip";
import { execFileSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseYaml } from "yaml";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const REPO_ROOT = resolve(__dirname, "..", "..");
const INBOX = join(REPO_ROOT, "content", "inbox");
const UNITS_DIR = join(REPO_ROOT, "content", "units");
const PDFS_OUT = join(REPO_ROOT, "app", "public", "pdfs");
const ERRORS_DIR = join(INBOX, "errors");
const PROCESSED_DIR = join(INBOX, "processed");

export const FILENAME_RE = /^unit-(\d{2})-([a-z0-9-]+)\.zip$/;
export const REQUIRED_FILES = [
  "unit.yaml",
  "education.pdf",
  "projects.md",
  "tests/test_runner.py",
  "reference/pass_final.zip",
] as const;

export interface UnitYaml {
  order: number;
  slug: string;
  title: string;
  description: string;
  tags?: string[];
  duration_minutes?: number | null;
  published?: boolean;
  test_groups?: { name: string; weight?: number; order: number }[];
}

export interface VideosYaml {
  videos: {
    title: string;
    youtube_id: string;
    duration_seconds?: number;
    order: number;
    pdf_path?: string;
  }[];
}

export interface IngestOptions {
  dryRun?: boolean;
  inboxDir?: string;
  unitsDir?: string;
  pdfsOutDir?: string;
  runnerCli?: string;
  seccompProfile?: string;
  /** When true (test mode), skip the sandbox reference run. */
  skipReferenceCheck?: boolean;
}

export type IngestOutcome =
  | { kind: "ingested"; zipName: string; slug: string; order: number }
  | { kind: "dry-run-ok"; zipName: string; slug: string; order: number }
  | { kind: "rejected"; zipName: string; reason: string };

// ---------------------------------------------------------------------------
// Pure validators (exported for tests)
// ---------------------------------------------------------------------------

export function parseFilename(zipName: string): { order: number; slug: string } {
  const m = FILENAME_RE.exec(zipName);
  if (!m) {
    throw new Error(
      `filename does not match ^unit-NN-slug.zip$ (got: ${zipName})`,
    );
  }
  return { order: parseInt(m[1]!, 10), slug: m[2]! };
}

export function assertRequiredFiles(extractedRoot: string): void {
  for (const f of REQUIRED_FILES) {
    if (!existsSync(join(extractedRoot, f))) {
      throw new Error(`missing required file: ${f}`);
    }
  }
}

export function assertUnitYamlMatches(
  parsed: UnitYaml,
  filenameSlug: string,
  filenameOrder: number,
): void {
  if (typeof parsed.slug !== "string" || parsed.slug !== filenameSlug) {
    throw new Error(
      `unit.yaml slug "${parsed.slug}" does not match filename slug "${filenameSlug}"`,
    );
  }
  if (Number(parsed.order) !== filenameOrder) {
    throw new Error(
      `unit.yaml order ${parsed.order} does not match filename order ${filenameOrder}`,
    );
  }
  if (typeof parsed.title !== "string" || parsed.title.length === 0) {
    throw new Error("unit.yaml: title is required (non-empty string)");
  }
  if (typeof parsed.description !== "string") {
    throw new Error("unit.yaml: description is required");
  }
  if (parsed.test_groups !== undefined && !Array.isArray(parsed.test_groups)) {
    throw new Error("unit.yaml: test_groups must be a list");
  }
}

// ---------------------------------------------------------------------------
// Orchestration
// ---------------------------------------------------------------------------

export async function ingestAll(
  options: IngestOptions = {},
): Promise<IngestOutcome[]> {
  const inbox = options.inboxDir ?? INBOX;
  ensureDir(inbox);
  ensureDir(options.unitsDir ?? UNITS_DIR);
  ensureDir(options.pdfsOutDir ?? PDFS_OUT);
  ensureDir(join(inbox, "errors"));
  ensureDir(join(inbox, "processed"));

  const zips = readdirSync(inbox)
    .filter((f) => f.endsWith(".zip") && !f.startsWith("."))
    .sort();

  const outcomes: IngestOutcome[] = [];
  for (const zipName of zips) {
    try {
      outcomes.push(await ingestOne(zipName, options));
    } catch (e) {
      const reason = (e as Error).message;
      outcomes.push({ kind: "rejected", zipName, reason });
      writeErrorLog(inbox, zipName, e as Error);
    }
  }
  return outcomes;
}

export async function ingestOne(
  zipName: string,
  options: IngestOptions = {},
): Promise<IngestOutcome> {
  const inbox = options.inboxDir ?? INBOX;
  const unitsDir = options.unitsDir ?? UNITS_DIR;
  const pdfsOut = options.pdfsOutDir ?? PDFS_OUT;
  const dryRun = options.dryRun ?? false;

  const { order, slug } = parseFilename(zipName);
  const zipPath = join(inbox, zipName);
  if (!existsSync(zipPath)) throw new Error(`zip not found: ${zipPath}`);

  const tmpRoot = mkdtempSync(join(tmpdir(), `iau-ingest-${slug}-`));
  try {
    const extracted = join(tmpRoot, "unit");
    mkdirSync(extracted, { recursive: true });
    new AdmZip(zipPath).extractAllTo(extracted, true);

    assertRequiredFiles(extracted);

    const unitYaml = parseYaml(
      readFileSync(join(extracted, "unit.yaml"), "utf8"),
    ) as UnitYaml;
    assertUnitYamlMatches(unitYaml, slug, order);

    const videosYamlPath = join(extracted, "videos.yaml");
    let videosYaml: VideosYaml | null = null;
    if (existsSync(videosYamlPath)) {
      videosYaml = parseYaml(readFileSync(videosYamlPath, "utf8")) as VideosYaml;
      if (!videosYaml || !Array.isArray(videosYaml.videos)) {
        throw new Error("videos.yaml must contain a `videos:` list");
      }
    }

    if (!options.skipReferenceCheck) {
      await runReferenceCheck(extracted, tmpRoot, options);
    }

    if (dryRun) {
      return { kind: "dry-run-ok", zipName, slug, order };
    }

    // From here on we mutate. Each step is independent enough that on a
    // crash the operator can re-run; idempotency is provided by upsert.
    const projectsMd = readFileSync(join(extracted, "projects.md"), "utf8");
    await upsertUnitInDb(unitYaml, videosYaml, projectsMd, slug, order);

    const targetDir = join(unitsDir, `unit-${pad2(order)}-${slug}`);
    if (existsSync(targetDir)) rmSync(targetDir, { recursive: true });
    mkdirSync(dirname(targetDir), { recursive: true });
    cpSync(extracted, targetDir, { recursive: true });

    cpSync(
      join(extracted, "education.pdf"),
      join(pdfsOut, `${slug}.pdf`),
    );

    const processed = join(inbox, "processed");
    ensureDir(processed);
    renameSync(zipPath, join(processed, zipName));

    return { kind: "ingested", zipName, slug, order };
  } finally {
    rmSync(tmpRoot, { recursive: true, force: true });
  }
}

async function runReferenceCheck(
  extracted: string,
  tmpRoot: string,
  options: IngestOptions,
): Promise<void> {
  const refExtractDir = join(tmpRoot, "reference-extracted");
  mkdirSync(refExtractDir, { recursive: true });
  new AdmZip(join(extracted, "reference", "pass_final.zip")).extractAllTo(
    refExtractDir,
    true,
  );

  const runnerCli =
    options.runnerCli ?? join(REPO_ROOT, "runner", "src", "cli.ts");
  const seccomp =
    options.seccompProfile ?? join(REPO_ROOT, "infra", "seccomp.json");

  const stdout = execFileSync(
    "node",
    [
      "--experimental-strip-types",
      "--no-warnings=ExperimentalWarning",
      runnerCli,
      "--tests",
      join(extracted, "tests"),
      "--code",
      refExtractDir,
      "--seccomp",
      seccomp,
    ],
    { encoding: "utf8" },
  );

  let outcome: { kind: string; report?: { summary?: { verdict?: string } } };
  try {
    outcome = JSON.parse(stdout);
  } catch {
    throw new Error(`runner returned non-JSON output: ${stdout.slice(0, 200)}`);
  }

  if (outcome.kind !== "ok") {
    throw new Error(
      `reference solution sandbox outcome was not "ok" (got "${outcome.kind}"); reference is broken`,
    );
  }
  if (outcome.report?.summary?.verdict !== "passed") {
    throw new Error(
      `reference solution did not pass all tests (verdict=${outcome.report?.summary?.verdict}); reference is broken`,
    );
  }
}

async function upsertUnitInDb(
  unitYaml: UnitYaml,
  videosYaml: VideosYaml | null,
  projectsMd: string,
  slug: string,
  order: number,
): Promise<void> {
  // Lazy-import so unit tests that pass `skipReferenceCheck` and
  // `dryRun: true` never need a live database.
  const { PrismaClient } = await import("@prisma/client");
  const prisma = new PrismaClient();
  try {
    await prisma.$transaction(async (tx) => {
      const unit = await tx.unit.upsert({
        where: { slug },
        create: {
          slug,
          order,
          title: unitYaml.title,
          description: unitYaml.description,
          tags: unitYaml.tags ?? [],
          durationMinutes: unitYaml.duration_minutes ?? null,
          published: unitYaml.published ?? false,
        },
        update: {
          order,
          title: unitYaml.title,
          description: unitYaml.description,
          tags: unitYaml.tags ?? [],
          durationMinutes: unitYaml.duration_minutes ?? null,
          published: unitYaml.published ?? false,
        },
      });

      // Replace test groups wholesale — re-running ingest for the same unit
      // means the schema changed in unit.yaml; cascading delete handles
      // dependent TestCase + SubmissionTestResult rows for stale data.
      await tx.testGroup.deleteMany({ where: { unitId: unit.id } });
      for (const g of unitYaml.test_groups ?? []) {
        await tx.testGroup.create({
          data: {
            unitId: unit.id,
            name: g.name,
            order: g.order,
            weight: g.weight ?? 1,
          },
        });
      }

      // Replace videos
      await tx.video.deleteMany({ where: { unitId: unit.id } });
      if (videosYaml) {
        for (const v of videosYaml.videos) {
          await tx.video.create({
            data: {
              unitId: unit.id,
              title: v.title,
              youtubeId: v.youtube_id,
              order: v.order,
              pdfPath: v.pdf_path ?? null,
            },
          });
        }
      }

      // Single Project per unit (one projects.md), title mirrors the unit.
      await tx.project.deleteMany({ where: { unitId: unit.id } });
      await tx.project.create({
        data: {
          unitId: unit.id,
          title: unitYaml.title,
          markdownContent: projectsMd,
          order: 0,
        },
      });
    });
  } finally {
    await prisma.$disconnect();
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ensureDir(p: string): void {
  if (!existsSync(p)) mkdirSync(p, { recursive: true });
}

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function writeErrorLog(inbox: string, zipName: string, e: Error): void {
  const errorsDir = join(inbox, "errors");
  ensureDir(errorsDir);
  const stamp = new Date().toISOString();
  const body =
    `[${stamp}] ingest failed for ${zipName}\n${e.message}\n\n${e.stack ?? ""}\n`;
  writeFileSync(join(errorsDir, `${zipName}.log`), body);
}

// ---------------------------------------------------------------------------
// CLI entry
// ---------------------------------------------------------------------------

async function cli(): Promise<number> {
  const dryRun = process.argv.includes("--dry-run");
  const outcomes = await ingestAll({ dryRun });
  for (const o of outcomes) {
    if (o.kind === "ingested") {
      console.log(`[ingested] ${o.zipName} (slug=${o.slug}, order=${o.order})`);
    } else if (o.kind === "dry-run-ok") {
      console.log(`[dry-run] ${o.zipName} OK`);
    } else {
      console.error(`[rejected] ${o.zipName}: ${o.reason}`);
    }
  }
  const rejected = outcomes.filter((o) => o.kind === "rejected").length;
  return rejected === 0 ? 0 : 1;
}

if (
  process.argv[1] !== undefined &&
  resolve(process.argv[1]) === resolve(__filename)
) {
  cli().then((code) => process.exit(code));
}
