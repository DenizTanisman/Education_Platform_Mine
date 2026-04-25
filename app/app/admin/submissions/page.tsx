import Link from "next/link";

import { prisma } from "@/lib/db";

export default async function AdminSubmissionsPage(): Promise<React.ReactElement> {
  const subs = await prisma.submission.findMany({
    orderBy: { createdAt: "desc" },
    include: {
      user: { select: { email: true } },
      unit: { select: { slug: true, title: true, order: true } },
    },
    take: 200,
  });

  return (
    <div>
      <h1>Tüm denemeler</h1>
      <p className="muted">Son 200 deneme.</p>
      {subs.length === 0 ? (
        <p className="muted">Henüz hiç deneme yok.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Tarih</th>
              <th>Kullanıcı</th>
              <th>Ünite</th>
              <th>Durum</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {subs.map((s) => (
              <tr key={s.id}>
                <td>{s.createdAt.toLocaleString("tr-TR")}</td>
                <td>{s.user.email}</td>
                <td>{s.unit.order.toString().padStart(2, "0")} — {s.unit.title}</td>
                <td>{s.status}</td>
                <td><Link href={`/submissions/${s.id}`}>Detay →</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
