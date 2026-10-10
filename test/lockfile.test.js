import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parsePackageLock, parsePnpmLock, parsePnpmKey, parseLockfile } from "../src/lockfile.js";

const fx = (f) => readFileSync(new URL(`./fixtures/${f}`, import.meta.url), "utf8");
const ids = (r) => r.entries.map((e) => `${e.name}@${e.version}`);

test("package-lock v3: registry entries, aliases resolved, links/git/bundled skipped, deduped", () => {
  const r = parsePackageLock(fx("package-lock-v3.json"));
  assert.equal(r.lockfileVersion, 3);
  assert.deepEqual(ids(r), ["@babel/core@7.24.0", "left-pad@1.3.0", "picomatch@4.0.2", "vite@8.3.4"]);
  const reasons = Object.fromEntries(r.skipped.map((s) => [s.key, s.reason]));
  assert.equal(reasons["node_modules/from-git"], "not from a registry");
  assert.equal(reasons["node_modules/local-lib"], "link");
  assert.equal(reasons["node_modules/bundler/node_modules/inner"], "bundled");
  assert.equal(reasons["packages/local-lib"], "workspace");
});

test("package-lock v1: nested dependencies and npm: aliases", () => {
  const r = parsePackageLock(fx("package-lock-v1.json"));
  assert.deepEqual(ids(r), ["debug@4.3.4", "left-pad@1.3.0", "ms@2.1.2"]);
  assert.equal(r.skipped.length, 1);
});

test("pnpm-lock v9: packages section only, tarball deps skipped", () => {
  const r = parsePnpmLock(fx("pnpm-lock-v9.yaml"));
  assert.equal(r.lockfileVersion, "9.0");
  assert.deepEqual(ids(r), ["@types/node@24.0.0", "picomatch@4.0.2", "vite@8.3.3"]);
  assert.equal(r.skipped.length, 1);
});

test("pnpm-lock v6: leading slash and peer suffix", () => {
  assert.deepEqual(ids(parsePnpmLock(fx("pnpm-lock-v6.yaml"))), ["@types/node@20.0.0", "vite@5.0.0"]);
});

test("pnpm-lock v5: slash-separated versions with _peer suffix", () => {
  assert.deepEqual(ids(parsePnpmLock(fx("pnpm-lock-v5.yaml"))), ["@babel/core@7.24.0", "react-dom@18.2.0", "react@18.2.0"]);
});

test("parsePnpmKey edge cases", () => {
  assert.deepEqual(parsePnpmKey("'@scope/pkg@1.2.3-beta.1'"), { name: "@scope/pkg", version: "1.2.3-beta.1" });
  assert.deepEqual(parsePnpmKey("/pkg@2.0.0(react@18.2.0)(react-dom@18.2.0)"), { name: "pkg", version: "2.0.0" });
  assert.equal(parsePnpmKey("pkg@file:../pkg"), null);
  assert.equal(parsePnpmKey("pkg@link:../pkg"), null);
});

test("parseLockfile picks the parser by name or content", () => {
  assert.equal(parseLockfile("pnpm-lock.yaml", fx("pnpm-lock-v9.yaml")).kind, "pnpm");
  assert.equal(parseLockfile("package-lock.json", fx("package-lock-v3.json")).kind, "npm");
  assert.equal(parseLockfile("lock.txt", fx("package-lock-v3.json")).kind, "npm");
  assert.throws(() => parsePackageLock("{}"), /Not a package-lock/);
});
