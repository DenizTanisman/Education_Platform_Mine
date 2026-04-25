import { NextResponse } from "next/server";

import { ingestAll } from "@/scripts/ingest-content";
import { getCurrentUser } from "@/lib/session";

// Run on Node runtime (we touch the filesystem and the docker daemon).
export const runtime = "nodejs";
// Long-running by design; the sandbox call alone can take ~10s per ZIP.
export const maxDuration = 600;

export async function POST(req: Request): Promise<NextResponse> {
  const user = await getCurrentUser();
  if (!user || user.role !== "ADMIN") {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  const dryRun = new URL(req.url).searchParams.get("dry-run") === "1";

  // Capture console output during the ingest run so the UI can show what
  // happened. We swap console.log/.error into a buffer for the duration.
  const buf: string[] = [];
  const origLog = console.log;
  const origErr = console.error;
  console.log = (...args: unknown[]) => buf.push(args.map(String).join(" "));
  console.error = (...args: unknown[]) => buf.push("[err] " + args.map(String).join(" "));

  let outcomes;
  try {
    outcomes = await ingestAll({ dryRun });
  } catch (e) {
    console.log = origLog;
    console.error = origErr;
    return NextResponse.json(
      { error: (e as Error).message, log: buf.join("\n") },
      { status: 500 },
    );
  }
  console.log = origLog;
  console.error = origErr;

  return NextResponse.json({
    outcomes: outcomes.map((o) =>
      o.kind === "rejected"
        ? { kind: o.kind, zipName: o.zipName, reason: o.reason }
        : { kind: o.kind, zipName: o.zipName, slug: o.slug },
    ),
    log: buf.join("\n"),
  });
}
