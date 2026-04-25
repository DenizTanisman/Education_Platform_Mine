/**
 * Read-side helpers for unit + progress data. Centralised so the
 * dashboard, the education page, and the API routes share one
 * source of truth for the locked / in_progress / completed rule.
 */
import { prisma } from "./db";

export type UnitStatus = "LOCKED" | "IN_PROGRESS" | "COMPLETED";

export interface UnitForDashboard {
  id: string;
  slug: string;
  order: number;
  title: string;
  description: string;
  status: UnitStatus;
}

/**
 * Returns every published unit in `order` ascending, joined with the
 * caller's progress. The implicit unlock rule:
 *   - the lowest-order unit is always at least IN_PROGRESS
 *   - a unit is unlocked once the previous one is COMPLETED
 *   - everything else is LOCKED until that gate opens
 */
export async function listUnitsForUser(userId: string): Promise<UnitForDashboard[]> {
  const [units, progress] = await Promise.all([
    prisma.unit.findMany({
      where: { published: true },
      orderBy: { order: "asc" },
      select: { id: true, slug: true, order: true, title: true, description: true },
    }),
    prisma.unitProgress.findMany({
      where: { userId },
      select: { unitId: true, status: true },
    }),
  ]);

  const progressMap = new Map(progress.map((p) => [p.unitId, p.status]));
  let prevCompleted = true; // first unit is unlocked by default

  return units.map((u) => {
    const explicit = progressMap.get(u.id);
    const status: UnitStatus = (() => {
      if (explicit === "COMPLETED") return "COMPLETED";
      if (explicit === "IN_PROGRESS") return "IN_PROGRESS";
      if (prevCompleted) return "IN_PROGRESS";
      return "LOCKED";
    })();
    prevCompleted = status === "COMPLETED";
    return { ...u, status };
  });
}

export async function getUnitForUser(
  userId: string,
  slug: string,
): Promise<{
  id: string;
  slug: string;
  order: number;
  title: string;
  description: string;
  status: UnitStatus;
  videos: { id: string; title: string; youtubeId: string; order: number }[];
  projectsMarkdown: string;
} | null> {
  const unit = await prisma.unit.findUnique({
    where: { slug },
    include: {
      videos: { orderBy: { order: "asc" } },
      projects: { orderBy: { order: "asc" }, take: 1 },
    },
  });
  if (!unit || !unit.published) return null;

  const all = await listUnitsForUser(userId);
  const own = all.find((u) => u.id === unit.id);
  if (!own || own.status === "LOCKED") return null;

  return {
    id: unit.id,
    slug: unit.slug,
    order: unit.order,
    title: unit.title,
    description: unit.description,
    status: own.status,
    videos: unit.videos.map((v) => ({
      id: v.id,
      title: v.title,
      youtubeId: v.youtubeId,
      order: v.order,
    })),
    projectsMarkdown: unit.projects[0]?.markdownContent ?? "",
  };
}
