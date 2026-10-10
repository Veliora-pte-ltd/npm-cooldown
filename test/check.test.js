import { test } from "node:test";
import assert from "node:assert/strict";
import { checkEntries } from "../src/check.js";
import { packumentUrl, fetchPublishTimes } from "../src/registry.js";

const now = new Date("2026-10-08T16:54:16Z");
// vite publish times as recorded on 8 October 2026 (see data/results/cooldown-check.txt)
const TIMES = {
  vite: { "8.3.4": "2026-10-08T12:07:04.441Z", "8.3.3": "2026-10-06T04:10:19.326Z", "8.3.2": "2026-10-01T10:17:44.767Z" },
  picomatch: { "4.0.2": "2024-03-28T00:00:00.000Z" },
};
const fakeTimes = async (name) => {
  if (name === "boom") throw new Error("network down");
  return TIMES[name] ?? null;
};

test("flags versions younger than the cooldown, oldest-safe ones pass", async () => {
  const entries = [{ name: "vite", version: "8.3.4" }, { name: "vite", version: "8.3.3" }, { name: "vite", version: "8.3.2" }, { name: "picomatch", version: "4.0.2" }];
  const r = await checkEntries(entries, { days: 7, now, fetchTimes: fakeTimes });
  assert.deepEqual(r.flagged.map((f) => f.version), ["8.3.4", "8.3.3"]);
  assert.equal(r.flagged[0].ageDays, 0.2);
  assert.equal(r.ok, 2);
  const r1 = await checkEntries(entries, { days: 1, now, fetchTimes: fakeTimes });
  assert.deepEqual(r1.flagged.map((f) => f.version), ["8.3.4"]);
  const r0 = await checkEntries(entries, { days: 0, now, fetchTimes: fakeTimes });
  assert.equal(r0.flagged.length, 0);
});

test("unknown versions, missing packages and errors are reported separately", async () => {
  const r = await checkEntries([{ name: "vite", version: "9.9.9" }, { name: "gone", version: "1.0.0" }, { name: "boom", version: "1.0.0" }], { now, fetchTimes: fakeTimes });
  assert.equal(r.flagged.length, 0);
  assert.deepEqual(r.unknown.map((u) => u.reason), ["no publish time for this version", "package not found on the registry"]);
  assert.deepEqual(r.errors, [{ name: "boom", error: "network down" }]);
});

test("one registry request per package name", async () => {
  let calls = 0;
  await checkEntries([{ name: "vite", version: "8.3.4" }, { name: "vite", version: "8.3.2" }], { now, fetchTimes: async (n) => { calls++; return TIMES[n]; } });
  assert.equal(calls, 1);
});

test("packument URLs: scoped names encoded, tarball paths refused", () => {
  assert.equal(packumentUrl("@babel/core"), "https://registry.npmjs.org/@babel%2Fcore");
  assert.equal(packumentUrl("vite", "https://npm.example.com/repo"), "https://npm.example.com/repo/vite");
  assert.throws(() => packumentUrl("vite/-/vite-8.3.4.tgz"), /Refusing/);
});

test("fetchPublishTimes returns the time map and null on 404", async () => {
  const seen = [];
  const fetchImpl = async (url) => {
    seen.push(url);
    if (url.endsWith("/missing")) return { status: 404, ok: false };
    return { status: 200, ok: true, json: async () => ({ name: "vite", time: TIMES.vite }) };
  };
  assert.deepEqual(await fetchPublishTimes("vite", { fetchImpl }), TIMES.vite);
  assert.equal(await fetchPublishTimes("missing", { fetchImpl }), null);
  assert.deepEqual(seen, ["https://registry.npmjs.org/vite", "https://registry.npmjs.org/missing"]);
});
