#!/usr/bin/env python3
"""RQ6 follow-up: the two apps whose `npm ci` failed with EALLOWGIT under npm 12 defaults are re-run
with the one opt-in that error asks for (--allow-git=all), same bubblewrap sandbox as friction.py,
to see what else npm 12 then blocks. Clones from friction.py are reused (same commits)."""
import json, re, subprocess, sys, time, os
W = os.environ.get("FRICTION_WORKDIR", "/tmp/npm12-friction")
SB = sys.argv[1]; OUT = sys.argv[2]
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
    except subprocess.TimeoutExpired:
        return "timeout", "", timeout
res = []
for name in ("insomnia", "desktop"):
    d = f"{W}/apps/{name}"
    r = {"app": name, "commit": subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()}
    r["ci_exit"], log, r["ci_secs"] = bw(d, f"{NPM} ci --no-audit --no-fund --allow-git=all 2>&1", 1500)
    r["ci_log_tail"] = log[-2000:]
    _, ls, _ = bw(d, f"{NPM} install-scripts ls 2>&1", 300)
    r["blocked_ls"] = ls[-4000:]
    m = re.search(r"(\d+) packages? ha(?:s|ve) install scripts blocked", ls)
    r["n_blocked"] = int(m.group(1)) if m else None
    r["blocked_pkgs"] = re.findall(r"^\s+(\S+@\S+) \(", ls, re.M)
    subprocess.run(["rm", "-rf", f"{d}/node_modules"])
    print("done", name, r["ci_exit"], r["n_blocked"], flush=True); res.append(r)
json.dump(res, open(OUT, "w"), indent=1)
