import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";

export default async function SubmissionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const { id } = await params;
  const sub = await prisma.submission.findUnique({
    where: { id },
    include: {
      unit: { select: { slug: true, title: true, order: true } },
      results: {
        include: { testCase: { include: { testGroup: { select: { name: true } } } } },
      },
    },
  });
  if (!sub) notFound();
  if (sub.userId !== user.id && user.role !== "ADMIN") notFound();

  // group rows by testGroup.name
  const grouped = new Map<
    string,
    { id: string; status: string; detail: string | null; runtimeMs: number | null }[]
  >();
  for (const r of sub.results) {
    const name = r.testCase.testGroup.name;
    if (!grouped.has(name)) grouped.set(name, []);
    grouped.get(name)!.push({
      id: r.testCase.extId,
      status: r.status,
      detail: r.detail,
      runtimeMs: r.runtimeMs,
    });
  }

  return (
    <main>
      <p className="muted">
        <Link href={`/units/${sub.unit.slug}/submissions`}>← Geçmiş denemeler</Link>
      </p>
      <h1>{sub.unit.title} — deneme {sub.id.slice(-6)}</h1>
      <p>
        Tarih: {sub.createdAt.toLocaleString("tr-TR")} · Durum:{" "}
        <strong style={{ color: sub.status === "PASSED" ? "#3fb950" : "#f85149" }}>{sub.status}</strong>
      </p>

      {grouped.size === 0 ? (
        <div className="card">
          <p className="muted">Henüz test çıktısı kaydedilmemiş.</p>
          {sub.report ? (
            <pre>{JSON.stringify(sub.report, null, 2)}</pre>
          ) : null}
        </div>
      ) : (
        Array.from(grouped.entries()).map(([name, tests]) => (
          <div className="card" key={name}>
            <h2 style={{ marginTop: 0 }}>{name}</h2>
            {tests.map((t) => (
              <div key={t.id} className={`test-row ${t.status.toLowerCase()}`}>
                <div>
                  <strong>{t.id}</strong>
                  {t.detail !== null && <span className="muted"> — {t.detail}</span>}
                </div>
                <div>
                  {t.status} {t.runtimeMs !== null && <span className="muted">{t.runtimeMs}ms</span>}
                </div>
              </div>
            ))}
          </div>
        ))
      )}

      <p>
        <Link href={`/units/${sub.unit.slug}/final`}>
          <button type="button">Bu ünite için yeniden dene</button>
        </Link>
      </p>
    </main>
  );
}
