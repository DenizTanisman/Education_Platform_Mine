import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/session";
import { getUnitForUser } from "@/lib/units";

export default async function EducationPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const { slug } = await params;
  const unit = await getUnitForUser(user.id, slug);
  if (!unit) notFound();

  const orderStr = unit.order.toString().padStart(2, "0");

  return (
    <main>
      <p className="muted">
        <Link href="/dashboard">← Üniteler</Link>
      </p>
      <h1>
        Ünite {orderStr} — {unit.title}
      </h1>
      <p className="muted">{unit.description}</p>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 3fr) minmax(220px, 1fr)", gap: "1.5rem" }}>
        <section>
          <h2>Ders notu</h2>
          <iframe
            src={`/pdfs/${unit.slug}.pdf`}
            title={`${unit.title} education PDF`}
            style={{ width: "100%", height: "75vh", border: "1px solid var(--border)", borderRadius: 8 }}
          />

          {unit.videos.length > 0 && (
            <>
              <h2 style={{ marginTop: "2rem" }}>Videolar</h2>
              <div style={{ display: "grid", gap: "1rem" }}>
                {unit.videos.map((v) => (
                  <div key={v.id} className="card">
                    <h3 style={{ marginTop: 0 }}>{v.title}</h3>
                    <div style={{ position: "relative", paddingBottom: "56.25%", height: 0 }}>
                      <iframe
                        src={`https://www.youtube-nocookie.com/embed/${v.youtubeId}`}
                        title={v.title}
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: 0 }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        <aside>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Sonraki adım</h3>
            <p>
              <Link href={`/units/${unit.slug}/projects`}>Proje talimatları →</Link>
            </p>
            <p>
              <Link href={`/units/${unit.slug}/final`}>Final ZIP yükle →</Link>
            </p>
            <p>
              <Link href={`/units/${unit.slug}/submissions`}>Geçmiş denemeler →</Link>
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}
