import { NextResponse } from "next/server";

import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  const { id } = await params;
  const submission = await prisma.submission.findUnique({
    where: { id },
    include: {
      results: {
        include: { testCase: { include: { testGroup: true } } },
      },
      unit: { select: { slug: true, title: true, order: true } },
    },
  });
  if (!submission) return NextResponse.json({ error: "not_found" }, { status: 404 });

  // Hide other users' submissions; admins see everything.
  if (submission.userId !== user.id && user.role !== "ADMIN") {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  // Re-shape into the JSON the contract page expects.
  const grouped = new Map<
    string,
    {
      name: string;
      tests: { id: string; status: string; detail: string | null; runtimeMs: number | null }[];
    }
  >();
  for (const r of submission.results) {
    const groupName = r.testCase.testGroup.name;
    if (!grouped.has(groupName)) {
      grouped.set(groupName, { name: groupName, tests: [] });
    }
    grouped.get(groupName)!.tests.push({
      id: r.testCase.extId,
      status: r.status,
      detail: r.detail,
      runtimeMs: r.runtimeMs,
    });
  }

  return NextResponse.json({
    id: submission.id,
    unit: submission.unit,
    status: submission.status,
    createdAt: submission.createdAt,
    updatedAt: submission.updatedAt,
    report: submission.report,
    groups: Array.from(grouped.values()),
  });
}
