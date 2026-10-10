#!/usr/bin/env python3
"""RQ6 (secondary): npm 12 install-script friction on 10 benign open-source apps.

Each app is cloned (shallow, pinned to the default-branch HEAD at run time; the
commit is recorded) into a throwaway directory under /tmp, then every npm
command runs inside bubblewrap: read-only /usr and /etc, private /tmp, no
home or project directories (so no tokens, keys or git credentials are visible),
cleared environment (HOME = the temp dir; all other variables, including any API keys, unset), PID/IPC namespaces unshared. Network is shared (registry
access is needed). No root, no system packages installed.

Steps per app:
 1. npm ci under npm 12.2.0 defaults (dependency install scripts blocked)
 2. npm install-scripts ls  -> which packages were blocked
 3. npm run build (if the app has a build script)
 4. npm install-scripts approve --all ; npm rebuild ; npm run build again
"""
import json, os, re, subprocess, sys, time, shutil
from concurrent.futures import ThreadPoolExecutor
APPS = json.load(open(sys.argv[1])); OUT = sys.argv[2]
W = os.environ.get("FRICTION_WORKDIR", "/tmp/npm12-friction"); SB = sys.argv[3]  # sandbox tools dir (node + npm12)
NODE = f"{SB}/node-v24.21.0-linux-x64"; NPM = "node /opt/npm12/node_modules/npm/bin/npm-cli.js"
def bw(appdir, cmd, timeout):
    home = f"{appdir}/.home"; os.makedirs(home, exist_ok=True)
    argv = ["bwrap", "--ro-bind", "/usr", "/usr", "--ro-bind", "/etc", "/etc", "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/bin", "/bin", "--symlink", "usr/sbin", "/sbin",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", appdir, appdir,
            "--ro-bind", NODE, "/opt/node", "--ro-bind", f"{SB}/npm12", "/opt/npm12",
            "--unshare-pid", "--unshare-ipc", "--die-with-parent", "--clearenv",
            "--setenv", "HOME", home, "--setenv", "PATH", "/opt/node/bin:/usr/bin:/bin",
            "--setenv", "npm_config_cache", f"{home}/.npm", "--setenv", "CI", "true",
            "--chdir", appdir, "sh", "-c", cmd]
    t0 = time.time()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)[-6000:], round(time.time() - t0)
    except subprocess.TimeoutExpired as e:
        return "timeout", "", timeout
def run(app):
    name = app["repo"].split("/")[1]; d = f"{W}/apps/{name}"
    shutil.rmtree(d, ignore_errors=True); os.makedirs(os.path.dirname(d), exist_ok=True)
    r = {"repo": app["repo"], "category": app["category"], "subdir": app.get("subdir", "")}
    c = subprocess.run(["git", "clone", "--depth", "1", "-q", f"https://github.com/{app['repo']}.git", d], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "GIT_TERMINAL_PROMPT": "0"})
    if c.returncode: r["error"] = "clone failed: " + c.stderr[-300:]; return r
    r["commit"] = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    ad = os.path.join(d, app.get("subdir", ""))
    r["has_lockfile"] = os.path.exists(f"{ad}/package-lock.json")
    pj = json.load(open(f"{ad}/package.json")); r["has_build"] = "build" in pj.get("scripts", {})
    r["ci_exit"], log, r["ci_secs"] = bw(ad, f"{NPM} ci --no-audit --no-fund 2>&1", 1500)
    r["ci_log_tail"] = log[-1500:]
    _, ls, _ = bw(ad, f"{NPM} install-scripts ls 2>&1", 300)
    r["blocked_ls"] = ls[-4000:]
    m = re.search(r"(\d+) packages? ha(?:s|ve) install scripts blocked", ls)
    r["n_blocked"] = int(m.group(1)) if m else (0 if "No " in ls or not ls.strip() else None)
    r["blocked_pkgs"] = re.findall(r"^\s+(\S+@\S+) \(", ls, re.M)
    if r["has_build"] and r["ci_exit"] == 0:
        r["build_exit_blocked"], bl, r["build_secs_blocked"] = bw(ad, f"{NPM} run build 2>&1", 1200)
        r["build_log_tail_blocked"] = bl[-1500:]
    if r["n_blocked"]:
        r["approve_exit"], al, _ = bw(ad, f"{NPM} install-scripts approve --all 2>&1 && {NPM} rebuild 2>&1", 1200)
        r["approve_log_tail"] = al[-1500:]
        if r["has_build"]:
            r["build_exit_approved"], bl2, _ = bw(ad, f"{NPM} run build 2>&1", 1200)
            r["build_log_tail_approved"] = bl2[-1500:]
    try:
        r["allowScripts_entries"] = len(json.load(open(f"{ad}/package.json")).get("allowScripts", {}))
    except Exception: pass
    shutil.rmtree(f"{ad}/node_modules", ignore_errors=True)
    print("done", app["repo"], r.get("ci_exit"), r.get("n_blocked"), flush=True)
    return r
with ThreadPoolExecutor(3) as ex: res = list(ex.map(run, APPS))
json.dump(res, open(OUT, "w"), indent=1)
