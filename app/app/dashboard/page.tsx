// Replaced by Faz 6.1 with the real unit list. Until then, this just
// confirms the auth round-trip worked.
import { cookies } from "next/headers";
import Link from "next/link";

import { SESSION_COOKIE, verifySession } from "@/lib/auth";
import { prisma } from "@/lib/db";

export default async function DashboardPage(): Promise<React.ReactElement> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value ?? "";
  const claims = await verifySession(token);
  // middleware blocks this route for unauth, so claims is non-null in practice.
  const user = claims
    ? await prisma.user.findUnique({
        where: { id: claims.sub },
        select: { email: true, role: true },
      })
    : null;

  return (
    <main>
      <h1>Dashboard</h1>
      <p className="muted">
        Hoş geldin, {user?.email ?? "öğrenci"}. (Rol: {user?.role ?? "?"})
      </p>
      <div className="card">
        <p>Üniteler bu sayfada listelenecek (Faz 6.1).</p>
      </div>
      <form action="/api/logout" method="post">
        <button type="submit" className="secondary">Çıkış</button>
      </form>
    </main>
  );
}
