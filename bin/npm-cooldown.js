#!/usr/bin/env node
// Flag lockfile packages whose resolved version was published fewer than N days ago.
import { readFileSync, existsSync } from "node:fs";
import { basename } from "node:path";
import { parseArgs } from "node:util";
import { parseLockfile } from "../src/lockfile.js";
import { checkEntries } from "../src/check.js";
import { DEFAULT_REGISTRY } from "../src/registry.js";

const HELP = `Usage: npm-cooldown [lockfile] [options]

Reads package-lock.json, npm-shrinkwrap.json or pnpm-lock.yaml and lists every package whose
locked version was published on the registry fewer than N days ago.

  lockfile               path to the lockfile (default: ./package-lock.json, then ./pnpm-lock.yaml)
  -d, --days <n>         cooldown in days, decimals allowed (default: 7)
  -r, --registry <url>   registry to query (default: $npm_config_registry or ${DEFAULT_REGISTRY})
  -c, --concurrency <n>  parallel registry requests (default: 8)
      --json             machine-readable output
      --strict           also exit 1 when a version's publish time is unknown or a request fails
  -h, --help             show this help

Exit codes: 0 nothing flagged, 1 at least one package is newer than the cooldown, 2 usage or read error.
Only package metadata is requested; no package code is downloaded or run.`;

function fail(msg) { process.stderr.write(`npm-cooldown: ${msg}\n`); process.exit(2); }

let args;
try {
  args = parseArgs({ allowPositionals: true, options: {
    days: { type: "string", short: "d" }, registry: { type: "string", short: "r" },
    concurrency: { type: "string", short: "c" }, json: { type: "boolean" }, strict: { type: "boolean" },
    help: { type: "boolean", short: "h" } } });
} catch (e) { fail(e.message); }
const { values: o, positionals } = args;
if (o.help) { process.stdout.write(HELP + "\n"); process.exit(0); }

const file = positionals[0] || ["package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml"].find((f) => existsSync(f));
if (!file) fail("no lockfile given and none found in the current directory");
const days = o.days === undefined ? 7 : Number(o.days);
if (!Number.isFinite(days) || days < 0) fail(`--days must be a non-negative number, got ${o.days}`);
const concurrency = o.concurrency === undefined ? 8 : Number.parseInt(o.concurrency, 10);
if (!(concurrency >= 1)) fail("--concurrency must be at least 1");
const registry = o.registry || process.env.npm_config_registry || process.env.NPM_CONFIG_REGISTRY || DEFAULT_REGISTRY;

let parsed;
try { parsed = parseLockfile(basename(file), readFileSync(file, "utf8")); } catch (e) { fail(`cannot read ${file}: ${e.message}`); }

const res = await checkEntries(parsed.entries, { days, registry, concurrency });
const strictFail = o.strict && (res.unknown.length || res.errors.length);
if (o.json) {
  process.stdout.write(JSON.stringify({ lockfile: file, kind: parsed.kind, lockfileVersion: parsed.lockfileVersion, skipped: parsed.skipped.length, ...res }, null, 2) + "\n");
} else {
  const out = [];
  out.push(`Checked ${res.checked} packages from ${file} against ${registry} (cooldown: ${days} day${days === 1 ? "" : "s"}).`);
  if (parsed.skipped.length) out.push(`Skipped ${parsed.skipped.length} entries that are not registry versions (workspaces, links, git, file).`);
  if (res.flagged.length) {
    out.push("", `${res.flagged.length} package${res.flagged.length === 1 ? " was" : "s were"} published less than ${days} day${days === 1 ? "" : "s"} ago:`);
    const w = Math.max(...res.flagged.map((f) => `${f.name}@${f.version}`.length));
    for (const f of res.flagged) out.push(`  ${`${f.name}@${f.version}`.padEnd(w)}  published ${f.published.slice(0, 16)}Z  (${f.ageDays.toFixed(1)} days ago)`);
  } else out.push("", `Nothing in the lockfile is newer than ${days} day${days === 1 ? "" : "s"}.`);
  if (res.unknown.length) { out.push("", `${res.unknown.length} with no publish time (check these by hand):`); for (const u of res.unknown) out.push(`  ${u.name}@${u.version}: ${u.reason}`); }
  if (res.errors.length) { out.push("", `${res.errors.length} registry request${res.errors.length === 1 ? "" : "s"} failed:`); for (const e of res.errors) out.push(`  ${e.name}: ${e.error}`); }
  process.stdout.write(out.join("\n") + "\n");
}
process.exitCode = res.flagged.length || strictFail ? 1 : 0;
