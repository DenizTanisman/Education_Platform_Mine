-- 01_BUILD_PLAN.md §3.1: at most one in-flight submission per (user, unit).
-- Postgres partial unique index — Prisma core does not yet generate these.
-- Application-layer queueing (runner p-limit) is the primary guard;
-- this index is belt-and-suspenders for a runaway concurrent-write bug.
CREATE UNIQUE INDEX "submission_running_unique"
  ON "Submission" ("userId", "unitId")
  WHERE status = 'RUNNING';
