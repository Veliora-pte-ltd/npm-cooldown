import { fetchPublishTimes, DEFAULT_REGISTRY } from "./registry.js";

const DAY_MS = 86400000;

async function pool(items, limit, fn) {
  const out = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) { const i = next++; out[i] = await fn(items[i], i); }
  });
  await Promise.all(workers);
  return out;
}

/**
 * Check each { name, version } against its registry publish time.
 * flagged:   published less than `days` days before `now`
 * unknown:   no publish time for that version (unpublished, private registry without `time`, or 404)
 * errors:    the registry request failed
 */
export async function checkEntries(entries, { days = 7, now = new Date(), registry = DEFAULT_REGISTRY, concurrency = 8, fetchTimes = fetchPublishTimes, fetchImpl } = {}) {
  const byName = new Map();
  for (const e of entries) { if (!byName.has(e.name)) byName.set(e.name, []); byName.get(e.name).push(e.version); }
  const names = [...byName.keys()];
  const times = new Map();
  const errors = [];
  await pool(names, concurrency, async (name) => {
    try { times.set(name, await fetchTimes(name, { registry, ...(fetchImpl ? { fetchImpl } : {}) })); }
    catch (err) { errors.push({ name, error: String(err && err.message || err) }); }
  });
  const flagged = [], unknown = [], ok = [];
  const cutoff = now.getTime() - days * DAY_MS;
  for (const e of entries) {
    if (!times.has(e.name)) continue; // counted in errors
    const t = times.get(e.name);
    if (t === null) { unknown.push({ ...e, reason: "package not found on the registry" }); continue; }
    const iso = t[e.version];
    if (!iso) { unknown.push({ ...e, reason: "no publish time for this version" }); continue; }
    const published = new Date(iso);
    const ageDays = (now.getTime() - published.getTime()) / DAY_MS;
    const row = { ...e, published: published.toISOString(), ageDays: Math.round(ageDays * 100) / 100 };
    (published.getTime() > cutoff ? flagged : ok).push(row);
  }
  flagged.sort((a, b) => a.ageDays - b.ageDays);
  return { days, checkedAt: now.toISOString(), registry, checked: entries.length, flagged, unknown, errors, ok: ok.length };
}
