/**
 * Thin CLI around runSandbox so shell scripts (scripts/test-sandbox.sh, etc.)
 * can drive the wrapper without an HTTP service. Faz 4 will introduce the
 * real HTTP runner; this CLI is a debugging / manual-test convenience.
 *
 * Usage:
 *   node --experimental-strip-types src/cli.ts \
 *     --tests <dir> --code <dir> --seccomp <profile.json> \
 *     [--image <tag>] [--timeout-ms <ms>] [--memory-mb <n>] \
 *     [--cpus <n>] [--pids-limit <n>]
 *
 * Always exits 0 on a parsed report; non-zero only on argument errors. The
 * caller distinguishes pass/fail/timeout from the JSON's `kind` field.
 */

import { resolve } from "node:path";
import { runSandbox, type SandboxRunInput } from "./sandbox-runner.ts";

interface ParsedArgs {
  testsDir?: string;
  codeDir?: string;
  seccompProfile?: string;
  image?: string;
  timeoutMs?: number;
  memoryMb?: number;
  cpus?: number;
  pidsLimit?: number;
}

function parseArgs(argv: readonly string[]): ParsedArgs {
  const out: ParsedArgs = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (next === undefined && arg !== undefined && arg.startsWith("--")) {
      throw new Error(`missing value for ${arg}`);
    }
    switch (arg) {
      case "--tests":
        out.testsDir = resolve(next!);
        i++;
        break;
      case "--code":
        out.codeDir = resolve(next!);
        i++;
        break;
      case "--seccomp":
        out.seccompProfile = resolve(next!);
        i++;
        break;
      case "--image":
        out.image = next!;
        i++;
        break;
      case "--timeout-ms":
        out.timeoutMs = Number(next!);
        i++;
        break;
      case "--memory-mb":
        out.memoryMb = Number(next!);
        i++;
        break;
      case "--cpus":
        out.cpus = Number(next!);
        i++;
        break;
      case "--pids-limit":
        out.pidsLimit = Number(next!);
        i++;
        break;
      case "-h":
      case "--help":
        printHelp();
        process.exit(0);
      default:
        throw new Error(`unknown arg: ${arg}`);
    }
  }
  return out;
}

function printHelp(): void {
  process.stdout.write(
    "Usage: cli.ts --tests <dir> --code <dir> --seccomp <profile.json>\n" +
      "  [--image <tag>] [--timeout-ms <ms>] [--memory-mb <n>] [--cpus <n>] [--pids-limit <n>]\n",
  );
}

function main(): number {
  let args: ParsedArgs;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (e) {
    process.stderr.write(`error: ${(e as Error).message}\n`);
    printHelp();
    return 2;
  }
  if (!args.testsDir || !args.codeDir || !args.seccompProfile) {
    process.stderr.write("error: --tests, --code, and --seccomp are required\n");
    printHelp();
    return 2;
  }

  const input: SandboxRunInput = {
    testsDir: args.testsDir,
    codeDir: args.codeDir,
    seccompProfile: args.seccompProfile,
    ...(args.image !== undefined && { image: args.image }),
    ...(args.timeoutMs !== undefined && { timeoutMs: args.timeoutMs }),
    ...(args.memoryMb !== undefined && { memoryMb: args.memoryMb }),
    ...(args.cpus !== undefined && { cpus: args.cpus }),
    ...(args.pidsLimit !== undefined && { pidsLimit: args.pidsLimit }),
  };
  const outcome = runSandbox(input);
  process.stdout.write(JSON.stringify(outcome) + "\n");
  return 0;
}

process.exit(main());
