// Registry client: fetches package METADATA (the packument) only, never a tarball.

export const DEFAULT_REGISTRY = "https://registry.npmjs.org/";

export function packumentUrl(name, registry = DEFAULT_REGISTRY) {
  const base = registry.endsWith("/") ? registry : registry + "/";
  const path = name.startsWith("@") ? "@" + encodeURIComponent(name.slice(1)) : encodeURIComponent(name);
  const url = base + path;
  if (url.includes("/-/") || url.endsWith(".tgz")) throw new Error(`Refusing non-metadata URL: ${url}`);
  return url;
}

/**
 * Returns the packument `time` map ({ version: ISO date, created, modified }), or null on 404.
 * The abbreviated install metadata does not carry publish times, so the full document is requested.
 */
export async function fetchPublishTimes(name, { registry = DEFAULT_REGISTRY, fetchImpl = globalThis.fetch, timeoutMs = 30000, retries = 2 } = {}) {
  const url = packumentUrl(name, registry);
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetchImpl(url, {
        headers: { accept: "application/json", "user-agent": "npm-cooldown (+https://github.com/Veliora-pte-ltd/npm-cooldown)" },
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
      const doc = await res.json();
      return doc.time || {};
    } catch (err) {
      lastErr = err;
      if (attempt < retries) await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
    }
  }
  throw lastErr;
}
