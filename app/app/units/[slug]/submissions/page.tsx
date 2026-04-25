import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";

export default async function SubmissionsListPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const { slug } = await params;
  const unit = await prisma.unit.findUnique({
    where: { slug },
    select: { id: true, slug: true, title: true, order: true },
  });
  if (!unit) notFound();

  const subs = await prisma.submission.findMany({
    where: { userId: user.id, unitId: unit.id },
    orderBy: { createdAt: "desc" },
    select: { id: true, status: true, createdAt: true },
    take: 100,
  });

  return (
    <main>
      <p className="muted">
        <Link href={`/units/${unit.slug}`}>← Ünite</Link>
      </p>
      <h1>{unit.title} — Geçmiş denemeler</h1>

      {subs.length === 0 ? (
        <p className="muted">Henüz deneme yapmamışsın.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Tarih</th>
              <th>Durum</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {subs.map((s) => (
              <tr key={s.id}>
                <td>{s.createdAt.toLocaleString("tr-TR")}</td>
                <td>
                  <span
                    className={`test-row ${s.status === "PASSED" ? "passed" : s.status === "FAILED" || s.status === "ERRORED" ? "failed" : ""}`}
                    style={{ display: "inline", border: 0, padding: 0 }}
                  >
                    {s.status}
                  </span>
                </td>
                <td>
                  <Link href={`/submissions/${s.id}`}>Detay →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
