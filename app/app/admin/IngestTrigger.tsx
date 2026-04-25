"use client";

import { useState } from "react";

interface IngestResult {
  outcomes: { kind: string; zipName: string; reason?: string; slug?: string }[];
  log: string;
}

export function IngestTrigger(): React.ReactElement {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function trigger(dryRun: boolean): Promise<void> {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch(`/api/admin/ingest${dryRun ? "?dry-run=1" : ""}`, {
        method: "POST",
      });
      if (!r.ok) {
        const body = (await r.json().catch(() => ({}))) as { error?: string };
        throw new Error(body.error ?? `HTTP ${r.status}`);
      }
      setResult((await r.json()) as IngestResult);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2 style={{ marginTop: 0 }}>Content ingest</h2>
      <p className="muted">
        <code>content/inbox/*.zip</code> dizinini tara. Geçenler{" "}
        <code>processed/</code>&apos;a taşınır, hatalılar{" "}
        <code>errors/&lt;zip&gt;.log</code>&apos;a yazılır.
      </p>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button type="button" onClick={() => void trigger(false)} disabled={busy}>
          {busy ? "Tarıyor…" : "Tara ve uygula"}
        </button>
        <button type="button" className="secondary" onClick={() => void trigger(true)} disabled={busy}>
          Sadece doğrula (dry-run)
        </button>
      </div>
      {error !== null && <div className="error">{error}</div>}
      {result !== null && (
        <div style={{ marginTop: "1rem" }}>
          <strong>Sonuç:</strong>
          <ul>
            {result.outcomes.length === 0 && <li className="muted">Inbox boş.</li>}
            {result.outcomes.map((o) => (
              <li key={o.zipName}>
                {o.zipName}: <strong>{o.kind}</strong>
                {o.reason !== undefined && <span className="muted"> — {o.reason}</span>}
              </li>
            ))}
          </ul>
          {result.log && (
            <details>
              <summary>Stdout/stderr</summary>
              <pre>{result.log}</pre>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
