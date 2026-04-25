import { prisma } from "@/lib/db";

export default async function AdminAnalyticsPage(): Promise<React.ReactElement> {
  const [userCount, completedCount, submissionStats, perUnit] = await Promise.all([
    prisma.user.count(),
    prisma.unitProgress.count({ where: { status: "COMPLETED" } }),
    prisma.submission.groupBy({
      by: ["status"],
      _count: { _all: true },
    }),
    prisma.unit.findMany({
      orderBy: { order: "asc" },
      select: {
        id: true,
        slug: true,
        order: true,
        title: true,
        submissions: { select: { status: true } },
      },
    }),
  ]);

  const submissionTotals = Object.fromEntries(
    submissionStats.map((s) => [s.status, s._count._all]),
  );
  const totalSubmissions = Object.values(submissionTotals).reduce(
    (a, b) => a + (b as number),
    0,
  );
  const avgPerUser = userCount === 0 ? 0 : (totalSubmissions / userCount).toFixed(1);

  return (
    <div>
      <h1>Analitik</h1>

      <section className="card">
        <h2 style={{ marginTop: 0 }}>Genel</h2>
        <ul>
          <li>Toplam kullanıcı: <strong>{userCount}</strong></li>
          <li>Tamamlanan ünite (toplam): <strong>{completedCount}</strong></li>
          <li>Toplam deneme: <strong>{totalSubmissions}</strong></li>
          <li>Kullanıcı başına ortalama deneme: <strong>{avgPerUser}</strong></li>
          <li>
            Durum dağılımı:{" "}
            {Object.entries(submissionTotals).map(([s, c]) => (
              <span key={s} style={{ marginRight: "0.5rem" }}>
                {s}={c as number}
              </span>
            ))}
          </li>
        </ul>
      </section>

      <section className="card">
        <h2 style={{ marginTop: 0 }}>Ünite başına pass-rate</h2>
        {perUnit.length === 0 ? (
          <p className="muted">Henüz ünite yok.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Ünite</th>
                <th>Toplam deneme</th>
                <th>Pass</th>
                <th>Pass-rate</th>
              </tr>
            </thead>
            <tbody>
              {perUnit.map((u) => {
                const total = u.submissions.length;
                const passed = u.submissions.filter((s) => s.status === "PASSED").length;
                const rate = total === 0 ? "—" : `${((passed / total) * 100).toFixed(0)}%`;
                return (
                  <tr key={u.id}>
                    <td>{u.order.toString().padStart(2, "0")}</td>
                    <td>
                      <strong>{u.title}</strong>{" "}
                      <span className="muted"><code>{u.slug}</code></span>
                    </td>
                    <td>{total}</td>
                    <td>{passed}</td>
                    <td>{rate}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
