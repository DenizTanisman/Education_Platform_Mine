import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/session";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}): Promise<React.ReactElement> {
  // Middleware also enforces ADMIN, but defence-in-depth here protects
  // against accidental misconfiguration.
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/admin");
  if (user.role !== "ADMIN") redirect("/dashboard");

  return (
    <main>
      <header style={{ display: "flex", gap: "1rem", alignItems: "baseline", borderBottom: "1px solid var(--border)", paddingBottom: "0.5rem" }}>
        <strong>Admin</strong>
        <Link href="/admin">Dashboard</Link>
        <Link href="/admin/analytics">Analitik</Link>
        <Link href="/admin/submissions">Tüm denemeler</Link>
        <span className="muted" style={{ marginLeft: "auto" }}>{user.email}</span>
      </header>
      {children}
    </main>
  );
}
