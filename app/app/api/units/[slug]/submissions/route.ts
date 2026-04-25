import { createHash } from "node:crypto";

import { NextResponse } from "next/server";

import { prisma } from "@/lib/db";
import { dispatchToRunner } from "@/lib/runner-client";
import { getCurrentUser } from "@/lib/session";
import { getUnitForUser } from "@/lib/units";

// 10 MB cap matches the runner's request limit (00_MASTER_PROMPT.md §2.4
// covers file size validation; runner enforces too as belt + suspenders).
const MAX_ZIP_BYTES = 10 * 1024 * 1024;

export async function POST(
  req: Request,
  { params }: { params: Promise<{ slug: string }> },
): Promise<NextResponse> {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  const { slug } = await params;
  const unit = await getUnitForUser(user.id, slug, user.role);
  if (!unit) return NextResponse.json({ error: "unit_not_found_or_locked" }, { status: 404 });

  const form = await req.formData().catch(() => null);
  const file = form?.get("zip");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "missing_zip" }, { status: 400 });
  }
  if (!file.name.toLowerCase().endsWith(".zip")) {
    return NextResponse.json({ error: "invalid_extension" }, { status: 400 });
  }
  if (file.size === 0 || file.size > MAX_ZIP_BYTES) {
    return NextResponse.json({ error: "invalid_size" }, { status: 400 });
  }

  const buffer = Buffer.from(await file.arrayBuffer());
  const zipHash = createHash("sha256").update(buffer).digest("hex");

  // Reject if the user already has a RUNNING submission for this unit;
  // matches the partial unique index in app/prisma/migrations/.
  const inFlight = await prisma.submission.findFirst({
    where: { userId: user.id, unitId: unit.id, status: "RUNNING" },
    select: { id: true },
  });
  if (inFlight) {
    return NextResponse.json(
      { error: "submission_in_flight", submissionId: inFlight.id },
      { status: 409 },
    );
  }

  const submission = await prisma.submission.create({
    data: {
      userId: user.id,
      unitId: unit.id,
      status: "QUEUED",
      zipHash,
    },
    select: { id: true },
  });

  // Fire-and-forget — the runner writes the final status directly. We log
  // failures but don't surface them to the client; the polling endpoint
  // will eventually settle to status=ERRORED if the runner never replies.
  dispatchToRunner({
    submissionId: submission.id,
    userId: user.id,
    unitSlug: slug,
    zipBuffer: buffer,
  }).catch(async (err) => {
    console.error("[submissions] runner dispatch failed:", err);
    await prisma.submission
      .update({
        where: { id: submission.id },
        data: { status: "ERRORED", report: { error: String(err) } },
      })
      .catch(() => {});
  });

  return NextResponse.json({ submissionId: submission.id }, { status: 202 });
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ slug: string }> },
): Promise<NextResponse> {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  const { slug } = await params;
  const unit = await prisma.unit.findUnique({ where: { slug }, select: { id: true } });
  if (!unit) return NextResponse.json({ error: "unit_not_found" }, { status: 404 });

  const submissions = await prisma.submission.findMany({
    where: { userId: user.id, unitId: unit.id },
    orderBy: { createdAt: "desc" },
    select: { id: true, status: true, createdAt: true, zipHash: true },
    take: 50,
  });
  return NextResponse.json({ submissions });
}
