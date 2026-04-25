import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import ReactMarkdown from "react-markdown";

import { getCurrentUser } from "@/lib/session";
import { getUnitForUser } from "@/lib/units";

export default async function ProjectsPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const { slug } = await params;
  const unit = await getUnitForUser(user.id, slug);
  if (!unit) notFound();

  return (
    <main>
      <p className="muted">
        <Link href={`/units/${unit.slug}`}>← Ünite</Link>
      </p>
      <h1>{unit.title} — Projeler</h1>

      <article className="card">
        {unit.projectsMarkdown ? (
          <ReactMarkdown>{unit.projectsMarkdown}</ReactMarkdown>
        ) : (
          <p className="muted">Bu ünite için proje talimatı tanımlanmamış.</p>
        )}
      </article>

      <p>
        <Link href={`/units/${unit.slug}/final`}>
          <button type="button">Final&apos;e geç →</button>
        </Link>
      </p>
    </main>
  );
}
