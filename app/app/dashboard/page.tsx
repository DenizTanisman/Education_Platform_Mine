import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/session";
import { listUnitsForUser } from "@/lib/units";

export default async function DashboardPage(): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/dashboard");

  const units = await listUnitsForUser(user.id, user.role);

  return (
    <main>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1>Üniteler</h1>
          <p className="muted">{user.email}</p>
        </div>
        <form action="/api/logout" method="post">
          <button type="submit" className="secondary">Çıkış</button>
        </form>
      </header>

      {units.length === 0 ? (
        <div className="card">
          <p>Henüz yüklenmiş bir ünite yok. Yetkili sisteme içerik geldiğinde burada görünecek.</p>
        </div>
      ) : (
        <div className="unit-grid">
          {units.map((u) => (
            <UnitCard key={u.id} unit={u} />
          ))}
        </div>
      )}
    </main>
  );
}

function UnitCard({
  unit,
}: {
  unit: { slug: string; order: number; title: string; description: string; status: string };
}): React.ReactElement {
  const orderStr = unit.order.toString().padStart(2, "0");
  const labels: Record<string, string> = {
    LOCKED: "kilitli",
    IN_PROGRESS: "açık",
    COMPLETED: "tamamlandı",
  };
  const inner = (
    <>
      <span className="badge">{labels[unit.status] ?? unit.status}</span>
      <div className="muted" style={{ fontSize: "0.85em" }}>Ünite {orderStr}</div>
      <h3 style={{ margin: "0.25rem 0" }}>{unit.title}</h3>
      <p className="muted" style={{ marginTop: "0.25rem" }}>{unit.description}</p>
    </>
  );
  if (unit.status === "LOCKED") {
    return (
      <div className="unit-card" data-status={unit.status} aria-disabled>
        {inner}
      </div>
    );
  }
  return (
    <Link href={`/units/${unit.slug}`} className="unit-card" data-status={unit.status}>
      {inner}
    </Link>
  );
}
