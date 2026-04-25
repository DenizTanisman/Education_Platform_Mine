/**
 * Lazy Prisma singleton. Tests that don't need a DB skip `import("./db.ts")`.
 */
import { PrismaClient } from "@prisma/client";

let _prisma: PrismaClient | null = null;

export function prisma(): PrismaClient {
  if (_prisma === null) _prisma = new PrismaClient();
  return _prisma;
}

export async function disconnect(): Promise<void> {
  if (_prisma !== null) {
    await _prisma.$disconnect();
    _prisma = null;
  }
}
