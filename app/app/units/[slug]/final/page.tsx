import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/session";
import { getUnitForUser } from "@/lib/units";

import { FinalUploader } from "./FinalUploader";

export default async function FinalPage({
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
      <h1>{unit.title} — Final</h1>
      <p className="muted">
        ZIP&apos;ini yükle — testler otomatik koşar, sonuç birkaç saniye içinde
        bu sayfada görünür. Cooldown yok, istediğin kadar deneyebilirsin.
      </p>

      <FinalUploader slug={unit.slug} />

      <p style={{ marginTop: "2rem" }}>
        <Link href={`/units/${unit.slug}/submissions`}>Tüm geçmiş denemelerim →</Link>
      </p>
    </main>
  );
}
