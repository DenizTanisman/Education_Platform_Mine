"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

export default function LoginPage(): React.ReactElement {
  return (
    <Suspense fallback={<main><h1>Giriş yap</h1><p className="muted">Yükleniyor…</p></main>}>
      <LoginInner />
    </Suspense>
  );
}

function LoginInner(): React.ReactElement {
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next") ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(localiseError(body.error, res.status));
      }
      router.push(next);
      router.refresh();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Giriş yap</h1>
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
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button type="submit" disabled={busy}>
          {busy ? "Giriş yapılıyor…" : "Giriş yap"}
        </button>
        {error !== null && <div className="error">{error}</div>}
        <p style={{ marginTop: "1rem" }}>
          Hesabın yok mu? <Link href="/register">Kayıt ol</Link>
        </p>
      </form>
    </main>
  );
}

function localiseError(code: string | undefined, status: number): string {
  switch (code) {
    case "invalid_credentials":
      return "E-posta veya parola hatalı.";
    case "invalid_body":
      return "Geçersiz form.";
    case "too_many_requests":
      return "Çok fazla deneme. Bir saat sonra tekrar dene.";
    default:
      return `Giriş başarısız (HTTP ${status}).`;
  }
}
