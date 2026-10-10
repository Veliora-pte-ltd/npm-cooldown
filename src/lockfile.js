// Lockfile readers. No dependencies: package-lock.json is JSON, and pnpm-lock.yaml is read with a
// small line parser that only looks at the keys of the top-level `packages:` section.

const SEMVER = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

/** @typedef {{ name: string, version: string }} Entry */

function dedupe(entries) {
  const seen = new Map();
  for (const e of entries) seen.set(`${e.name}@${e.version}`, e);
  return [...seen.values()].sort((a, b) => (a.name + "@" + a.version).localeCompare(b.name + "@" + b.version));
}

function isRegistryResolved(resolved) {
  if (!resolved) return true; // lockfiles written with omit-lockfile-registry-resolved have no `resolved`
  return /^https?:\/\//.test(resolved) && !/^https?:\/\/(codeload\.)?github\.com\//.test(resolved);
}

/**
 * package-lock.json (lockfileVersion 2 and 3 via `packages`; version 1 via `dependencies`).
 * Skips the root project, workspace links, bundled dependencies and git/file/directory dependencies.
 * @returns {{ entries: Entry[], skipped: { key: string, reason: string }[], lockfileVersion: number }}
 */
export function parsePackageLock(text) {
  const lock = typeof text === "string" ? JSON.parse(text) : text;
  const v = Number(lock.lockfileVersion ?? 1);
  const entries = [];
  const skipped = [];
  if (lock.packages && v >= 2) {
    for (const [key, p] of Object.entries(lock.packages)) {
      if (key === "") continue;
      if (!key.includes("node_modules/")) { skipped.push({ key, reason: "workspace" }); continue; }
      if (p.link) { skipped.push({ key, reason: "link" }); continue; }
      if (p.inBundle) { skipped.push({ key, reason: "bundled" }); continue; }
      const name = p.name || key.slice(key.lastIndexOf("node_modules/") + "node_modules/".length);
      if (!p.version || !SEMVER.test(p.version) || !isRegistryResolved(p.resolved)) {
        skipped.push({ key, reason: "not from a registry" }); continue;
      }
      entries.push({ name, version: p.version });
    }
  } else if (lock.dependencies) {
    const walk = (deps) => {
      for (const [name, d] of Object.entries(deps || {})) {
        if (d.bundled) skipped.push({ key: name, reason: "bundled" });
        else if (d.version && SEMVER.test(d.version) && isRegistryResolved(d.resolved)) entries.push({ name, version: d.version });
        else if (d.version && d.version.startsWith("npm:")) {
          const m = d.version.slice(4).match(/^(@?[^@]+)@(.+)$/);
          if (m && SEMVER.test(m[2])) entries.push({ name: m[1], version: m[2] });
          else skipped.push({ key: name, reason: "not from a registry" });
        } else skipped.push({ key: name, reason: "not from a registry" });
        walk(d.dependencies);
      }
    };
    walk(lock.dependencies);
  } else {
    throw new Error("Not a package-lock.json: no `packages` or `dependencies` field");
  }
  return { entries: dedupe(entries), skipped, lockfileVersion: v };
}

/** Split a pnpm package key into name and version. Handles v9 (`name@1.0.0`), v6 (`/name@1.0.0(peer@1)`)
 * and v5 (`/name/1.0.0_peer@1`). Returns null for keys that are not registry versions. */
export function parsePnpmKey(rawKey) {
  let key = rawKey.trim().replace(/:$/, "").replace(/^['"]|['"]$/g, "");
  if (key.startsWith("/")) key = key.slice(1);
  key = key.replace(/\(.*$/, ""); // v6+/v9 peer suffix
  let name, version;
  const at = key.lastIndexOf("@");
  if (at > 0 && /^(@[^/@]+\/)?[^/@]+$/.test(key.slice(0, at))) {
    name = key.slice(0, at); version = key.slice(at + 1);
  }
  if (!name || !SEMVER.test(version || "")) {
    // v5: /name/1.0.0 or /@scope/name/1.0.0_peer@1
    const m = key.match(/^(@[^/]+\/[^/]+|[^/@][^/]*)\/([^/]+)$/);
    if (!m) return null;
    name = m[1]; version = m[2].replace(/_.*$/, "");
  }
  if (!SEMVER.test(version)) return null;
  return { name, version };
}

/**
 * pnpm-lock.yaml (lockfile v5.x, v6 and v9). Reads only the keys under the top-level `packages:` map.
 * @returns {{ entries: Entry[], skipped: { key: string, reason: string }[], lockfileVersion: string|null }}
 */
export function parsePnpmLock(text) {
  const lines = text.split(/\r?\n/);
  const vm = text.match(/^lockfileVersion:\s*['"]?([\d.]+)['"]?/m);
  const entries = [];
  const skipped = [];
  let inPackages = false;
  let indent = null;
  for (const line of lines) {
    if (/^\S/.test(line)) { inPackages = /^packages:\s*$/.test(line); indent = null; continue; }
    if (!inPackages || !line.trim() || line.trim().startsWith("#")) continue;
    const m = line.match(/^( +)(\S.*):\s*(\{.*\})?\s*$/);
    if (!m) continue;
    if (indent === null) indent = m[1].length;
    if (m[1].length !== indent) continue;
    const parsed = parsePnpmKey(m[2]);
    if (parsed) entries.push(parsed);
    else skipped.push({ key: m[2], reason: "not from a registry" });
  }
  if (!vm && entries.length === 0) throw new Error("Not a pnpm-lock.yaml: no lockfileVersion or packages");
  return { entries: dedupe(entries), skipped, lockfileVersion: vm ? vm[1] : null };
}

/** Pick a parser from the file name, falling back to sniffing the content. */
export function parseLockfile(fileName, text) {
  if (/pnpm-lock\.ya?ml$/.test(fileName)) return { kind: "pnpm", ...parsePnpmLock(text) };
  if (/(package-lock|npm-shrinkwrap)\.json$/.test(fileName)) return { kind: "npm", ...parsePackageLock(text) };
  const t = text.trimStart();
  if (t.startsWith("{")) return { kind: "npm", ...parsePackageLock(t) };
  return { kind: "pnpm", ...parsePnpmLock(text) };
}
