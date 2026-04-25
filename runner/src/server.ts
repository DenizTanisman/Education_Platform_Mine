/**
 * Express server exposing the runner over HTTP.
 *
 * Endpoints:
 *   GET  /healthz         — liveness + queue stats
 *   POST /run             — queue a submission (multipart with `zip` field)
 *
 * Auth: a single shared secret in the `x-runner-secret` header. The app
 * service in Faz 5+ holds the same value (RUNNER_SHARED_SECRET in .env)
 * and never lets it leak to the browser.
 *
 * The 10 MB request size limit is enforced both at the Express body-parser
 * level and again as a sanity check inside the handler.
 */

import express, { type Request, type Response, type NextFunction } from "express";
import { z } from "zod";

import { runSubmission } from "./runner-core.ts";
import {
  getStats,
  MAX_QUEUED,
  QueueFullError,
  withQueueSlot,
} from "./queue.ts";

export const MAX_ZIP_BYTES = 10 * 1024 * 1024;

export interface AppOptions {
  /** Shared secret callers must echo in `x-runner-secret`. */
  readonly sharedSecret: string;
  /** Override paths for tests. */
  readonly seccompProfile?: string;
  readonly unitsDir?: string;
}

export function createApp(options: AppOptions): express.Express {
  const app = express();
  app.disable("x-powered-by");

  app.get("/healthz", (_req, res) => {
    res.json({ ok: true, ...getStats(), maxQueued: MAX_QUEUED });
  });

  // /run accepts JSON: { submissionId, userId, unitSlug, zipBase64 }.
  // Caller (app service) must base64-encode the upload buffer. This avoids
  // multer for now; we can swap in multipart later if memory pressure shows.
  app.post(
    "/run",
    express.json({ limit: MAX_ZIP_BYTES + 64 * 1024 }),
    requireSecret(options.sharedSecret),
    async (req, res, next) => {
      try {
        const input = parseRunInput(req);
        const result = await withQueueSlot(() =>
          runSubmission({
            submissionId: input.submissionId,
            userId: input.userId,
            unitSlug: input.unitSlug,
            zipBuffer: input.zipBuffer,
            ...(options.seccompProfile !== undefined && { seccompProfile: options.seccompProfile }),
            ...(options.unitsDir !== undefined && { unitsDir: options.unitsDir }),
          }),
        );
        res.json(result);
      } catch (e) {
        next(e);
      }
    },
  );

  app.use(errorMiddleware);

  return app;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const RunInputSchema = z.object({
  submissionId: z.string().min(1).max(64),
  userId: z.string().min(1).max(64),
  unitSlug: z.string().min(1).max(128),
  zipBase64: z.string().min(1),
});

interface RunInput {
  submissionId: string;
  userId: string;
  unitSlug: string;
  zipBuffer: Buffer;
}

function parseRunInput(req: Request): RunInput {
  // JSON variant
  if (req.is("application/json")) {
    const parsed = RunInputSchema.safeParse(req.body);
    if (!parsed.success) {
      throw new HttpError(400, "invalid request body", parsed.error.flatten());
    }
    const buf = Buffer.from(parsed.data.zipBase64, "base64");
    if (buf.length > MAX_ZIP_BYTES) {
      throw new HttpError(413, `zip too large (${buf.length} > ${MAX_ZIP_BYTES})`);
    }
    return {
      submissionId: parsed.data.submissionId,
      userId: parsed.data.userId,
      unitSlug: parsed.data.unitSlug,
      zipBuffer: buf,
    };
  }
  throw new HttpError(415, "unsupported content type; expected application/json");
}

function requireSecret(secret: string) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (secret === "") {
      next(new HttpError(500, "RUNNER_SHARED_SECRET not configured"));
      return;
    }
    const got = req.header("x-runner-secret") ?? "";
    if (!constantTimeEq(got, secret)) {
      next(new HttpError(401, "invalid runner secret"));
      return;
    }
    next();
  };
}

function constantTimeEq(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

class HttpError extends Error {
  readonly status: number;
  readonly details: unknown;
  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

function errorMiddleware(
  err: unknown,
  _req: Request,
  res: Response,
  _next: NextFunction,
): void {
  if (err instanceof QueueFullError) {
    res.status(429).json({ error: "queue full" });
    return;
  }
  if (err instanceof HttpError) {
    res
      .status(err.status)
      .json({ error: err.message, ...(err.details !== undefined && { details: err.details }) });
    return;
  }
  console.error("[runner] unhandled error:", err);
  res.status(500).json({ error: "internal" });
}

// ---------------------------------------------------------------------------
// Standalone entrypoint (not used by tests)
// ---------------------------------------------------------------------------

if (
  process.argv[1] !== undefined &&
  import.meta.url === `file://${process.argv[1]}`
) {
  const port = parseInt(process.env.RUNNER_PORT ?? "4000", 10);
  const secret = process.env.RUNNER_SHARED_SECRET ?? "";
  if (secret === "") {
    console.error("RUNNER_SHARED_SECRET is required");
    process.exit(1);
  }
  const app = createApp({ sharedSecret: secret });
  const server = app.listen(port, () => {
    console.log(`runner listening on :${port}`);
  });

  // Graceful shutdown — drains in-flight submissions before exiting.
  const shutdown = async (signal: string): Promise<void> => {
    console.log(`${signal} received, draining...`);
    server.close();
    const { waitForDrain } = await import("./queue.ts");
    const drained = await waitForDrain(30_000);
    console.log(`drained=${drained}, exiting`);
    process.exit(drained ? 0 : 1);
  };
  process.on("SIGTERM", () => void shutdown("SIGTERM"));
  process.on("SIGINT", () => void shutdown("SIGINT"));
}
