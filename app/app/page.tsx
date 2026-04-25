import Link from "next/link";

export default function HomePage(): React.ReactElement {
  return (
    <main>
      <h1>IAU AI Platform</h1>
      <p className="muted">Yapay zekayı pratikten öğrenmenin yolu.</p>
      <div className="card">
        <p>Devam etmek için giriş yapın veya kayıt olun.</p>
        <p>
          <Link href="/login">Giriş yap</Link>
          {" · "}
          <Link href="/register">Kayıt ol</Link>
        </p>
      </div>
    </main>
  );
}
