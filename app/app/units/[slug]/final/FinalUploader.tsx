"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const MAX_BYTES = 10 * 1024 * 1024;
const POLL_INTERVAL_MS = 1500;

interface SubmissionDetail {
  id: string;
  status: "QUEUED" | "RUNNING" | "PASSED" | "FAILED" | "ERRORED";
  groups: {
    name: string;
    tests: {
      id: string;
      status: "PASSED" | "FAILED" | "ERRORED" | "TIMEOUT";
      detail: string | null;
      runtimeMs: number | null;
    }[];
  }[];
  report: unknown;
}

export function FinalUploader({ slug }: { slug: string }): React.ReactElement {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SubmissionDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!submissionId) return;
    if (detail && (detail.status === "PASSED" || detail.status === "FAILED" || detail.status === "ERRORED")) {
      return;
    }
    let cancelled = false;
    const tick = async (): Promise<void> => {
      try {
        const r = await fetch(`/api/submissions/${submissionId}`, { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const body = (await r.json()) as SubmissionDetail;
        if (!cancelled) setDetail(body);
      } catch (e) {
        // transient — keep polling
        if (!cancelled) console.warn("poll error:", e);
      }
    };
    const id = setInterval(() => void tick(), POLL_INTERVAL_MS);
    void tick();
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [submissionId, detail?.status]);

  async function upload(file: File): Promise<void> {
    setError(null);
    if (!file.name.toLowerCase().endsWith(".zip")) {
      setError("Sadece .zip dosyası yükleyebilirsin.");
      return;
    }
    if (file.size === 0 || file.size > MAX_BYTES) {
      setError(`Dosya boyutu 1 byte ile ${MAX_BYTES / 1024 / 1024} MB arasında olmalı.`);
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.set("zip", file);
      const r = await fetch(`/api/units/${slug}/submissions`, {
        method: "POST",
        body: fd,
      });
      if (!r.ok) {
        const body = (await r.json().catch(() => ({}))) as { error?: string };
        throw new Error(localiseError(body.error, r.status));
      }
      const body = (await r.json()) as { submissionId: string };
      setSubmissionId(body.submissionId);
      setDetail(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) void upload(file);
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>): void {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    e.target.value = "";
  }

  return (
    <div>
      <div
        className={`dropzone ${dragOver ? "over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileInput.current?.click()}
        role="button"
        tabIndex={0}
        aria-busy={busy}
      >
        {busy ? "Yükleniyor…" : "ZIP&apos;i sürükle-bırak veya tıklayıp seç"}
        <input
          ref={fileInput}
          type="file"
          accept=".zip,application/zip"
          style={{ display: "none" }}
          onChange={onPick}
        />
      </div>
      {error !== null && <div className="error">{error}</div>}

      {submissionId && <ResultPanel slug={slug} detail={detail} />}
    </div>
  );
}

function ResultPanel({
  slug,
  detail,
}: {
  slug: string;
  detail: SubmissionDetail | null;
}): React.ReactElement {
  if (!detail || detail.status === "QUEUED" || detail.status === "RUNNING") {
    return (
      <div className="card">
        <p>
          Durum: <strong>{detail?.status ?? "QUEUED"}</strong>
        </p>
        <p className="muted">Test çalışıyor — sonuç birkaç saniye içinde gelir.</p>
      </div>
    );
  }
  return (
    <div className="card">
      <p>
        Sonuç:{" "}
        <strong style={{ color: detail.status === "PASSED" ? "#3fb950" : "#f85149" }}>
          {detail.status}
        </strong>
      </p>
      {detail.groups.map((g) => (
        <div key={g.name} style={{ marginTop: "1rem" }}>
          <h3 style={{ margin: "0 0 0.5rem" }}>{g.name}</h3>
          {g.tests.map((t) => (
            <div key={t.id} className={`test-row ${t.status.toLowerCase()}`}>
              <div>
                <strong>{t.id}</strong> {t.detail !== null && <span className="muted">— {t.detail}</span>}
              </div>
              <div>
                {t.status} {t.runtimeMs !== null && <span className="muted">{t.runtimeMs}ms</span>}
              </div>
            </div>
          ))}
        </div>
      ))}
      <p style={{ marginTop: "1.5rem" }}>
        <Link href={`/units/${slug}/final`}>
          <button type="button">Yeniden dene</button>
        </Link>
      </p>
    </div>
  );
}

function localiseError(code: string | undefined, status: number): string {
  switch (code) {
    case "missing_zip":
      return "ZIP dosyası eksik.";
    case "invalid_extension":
      return "Sadece .zip uzantılı dosyalar kabul ediliyor.";
    case "invalid_size":
      return "Dosya boyutu 1 byte ile 10 MB arasında olmalı.";
    case "submission_in_flight":
      return "Bu ünite için zaten çalışmakta olan bir denemen var.";
    case "unit_not_found_or_locked":
      return "Bu ünite henüz kilitli ya da yok.";
    default:
      return `Yükleme başarısız (HTTP ${status}).`;
  }
}
