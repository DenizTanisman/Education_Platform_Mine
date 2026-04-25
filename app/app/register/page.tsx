"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function RegisterPage(): React.ReactElement {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(localiseError(body.error, res.status));
      }
      router.push("/dashboard");
      router.refresh();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Kayıt ol</h1>
      <form className="card" onSubmit={onSubmit} aria-busy={busy}>
        <label htmlFor="email">E-posta</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <label htmlFor="password">Parola</label>
        <input
          id="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <p className="muted">En az 8 karakter.</p>

        <button type="submit" disabled={busy}>
          {busy ? "Kayıt yapılıyor…" : "Kayıt ol"}
        </button>
        {error !== null && <div className="error">{error}</div>}
        <p style={{ marginTop: "1rem" }}>
          Zaten hesabın var mı? <Link href="/login">Giriş yap</Link>
        </p>
      </form>
    </main>
  );
}

function localiseError(code: string | undefined, status: number): string {
  switch (code) {
    case "registration_failed":
      return "Bu e-posta zaten kayıtlı.";
    case "invalid_body":
      return "Geçersiz e-posta veya parola.";
    case "too_many_requests":
      return "Çok fazla deneme. Bir saat sonra tekrar dene.";
    default:
      return `Kayıt başarısız (HTTP ${status}).`;
  }
}
