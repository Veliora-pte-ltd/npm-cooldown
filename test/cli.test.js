import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const bin = fileURLToPath(new URL("../bin/npm-cooldown.js", import.meta.url));
const run = (...a) => spawnSync(process.execPath, [bin, ...a], { encoding: "utf8" });

test("--help exits 0", () => {
  const r = run("--help");
  assert.equal(r.status, 0);
  assert.match(r.stdout, /Usage: npm-cooldown/);
});

test("bad --days exits 2", () => {
  const r = run("test/fixtures/package-lock-v3.json", "--days", "soon");
  assert.equal(r.status, 2);
  assert.match(r.stderr, /--days must be/);
});

test("missing lockfile exits 2", () => {
  assert.equal(run("does-not-exist.json").status, 2);
});

// Live check against the public registry. Skipped unless NPM_COOLDOWN_LIVE=1.
test("live: an old lockfile has nothing flagged", { skip: process.env.NPM_COOLDOWN_LIVE !== "1" }, () => {
  const r = run("test/fixtures/package-lock-v1.json", "--json");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const out = JSON.parse(r.stdout);
  assert.equal(out.checked, 3);
  assert.equal(out.flagged.length, 0);
  assert.equal(out.errors.length, 0);
});
