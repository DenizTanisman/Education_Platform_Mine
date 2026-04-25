"use client";

import { useState } from "react";

interface Unit {
  id: string;
  slug: string;
  order: number;
  title: string;
  published: boolean;
}

interface UserRow {
  id: string;
  email: string;
  role: "STUDENT" | "ADMIN";
  createdAt: string;
}

export function UnitTogglesAndUsers({
  initialUnits,
  initialUsers,
}: {
  initialUnits: Unit[];
  initialUsers: UserRow[];
}): React.ReactElement {
  const [units, setUnits] = useState(initialUnits);
  const [users, setUsers] = useState(initialUsers);
  const [error, setError] = useState<string | null>(null);

  async function togglePublished(u: Unit): Promise<void> {
    setError(null);
    const next = !u.published;
    setUnits((prev) => prev.map((x) => (x.id === u.id ? { ...x, published: next } : x)));
    try {
      const r = await fetch(`/api/admin/units/${u.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ published: next }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    } catch (e) {
      setError((e as Error).message);
      // rollback
      setUnits((prev) => prev.map((x) => (x.id === u.id ? { ...x, published: u.published } : x)));
    }
  }

  async function changeRole(uRow: UserRow): Promise<void> {
    setError(null);
    const next = uRow.role === "ADMIN" ? "STUDENT" : "ADMIN";
    setUsers((prev) => prev.map((x) => (x.id === uRow.id ? { ...x, role: next } : x)));
    try {
      const r = await fetch(`/api/admin/users/${uRow.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ role: next }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    } catch (e) {
      setError((e as Error).message);
      setUsers((prev) => prev.map((x) => (x.id === uRow.id ? { ...x, role: uRow.role } : x)));
    }
  }

  return (
    <>
      <section className="card">
        <h2 style={{ marginTop: 0 }}>Üniteler</h2>
        {units.length === 0 ? (
          <p className="muted">Henüz ünite yok.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Slug</th>
                <th>Başlık</th>
                <th>Yayında</th>
              </tr>
            </thead>
            <tbody>
              {units.map((u) => (
                <tr key={u.id}>
                  <td>{u.order.toString().padStart(2, "0")}</td>
                  <td><code>{u.slug}</code></td>
                  <td>{u.title}</td>
                  <td>
                    <label style={{ display: "inline" }}>
                      <input
                        type="checkbox"
                        checked={u.published}
                        onChange={() => void togglePublished(u)}
                        style={{ width: "auto", marginRight: "0.5rem" }}
                      />
                      {u.published ? "açık" : "gizli"}
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h2 style={{ marginTop: 0 }}>Kullanıcılar</h2>
        <table>
          <thead>
            <tr>
              <th>E-posta</th>
              <th>Rol</th>
              <th>Kayıt</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td className="muted">{new Date(u.createdAt).toLocaleString("tr-TR")}</td>
                <td>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => void changeRole(u)}
                    style={{ width: "auto" }}
                  >
                    {u.role === "ADMIN" ? "Yetkiyi al" : "Admin yap"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {error !== null && <div className="error">{error}</div>}
    </>
  );
}
