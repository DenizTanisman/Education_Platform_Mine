/**
 * Tiny client that POSTs a submission to the runner service. Used by
 * /api/units/[slug]/submissions in fire-and-forget mode — the runner
 * updates the Submission row directly via Prisma, so the app doesn't
 * need the HTTP response body.
 */

interface DispatchInput {
  submissionId: string;
  userId: string;
  unitSlug: string;
  zipBuffer: Buffer;
}

export async function dispatchToRunner(input: DispatchInput): Promise<void> {
  const url = process.env.RUNNER_URL ?? "http://runner:4000";
  const secret = process.env.RUNNER_SHARED_SECRET ?? "";
  if (secret === "") {
    throw new Error("RUNNER_SHARED_SECRET not configured");
  }
  const res = await fetch(`${url}/run`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-runner-secret": secret,
    },
    body: JSON.stringify({
      submissionId: input.submissionId,
      userId: input.userId,
      unitSlug: input.unitSlug,
      zipBase64: input.zipBuffer.toString("base64"),
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`runner call failed: ${res.status} ${text}`);
  }
}
