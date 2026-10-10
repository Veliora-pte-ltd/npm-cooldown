#!/usr/bin/env python3
"""Summarise the RQ6 app run (results/friction.json + results/friction-followup.json) into
results/friction-summary.json. Exclusions are decided by the failure reason, recorded below."""
import json
R = json.load(open("data/results/friction.json")); F = {r["app"]: r for r in json.load(open("data/results/friction-followup.json"))}
EXCLUDE = {"typeorm/typeorm": "pnpm project (devEngines requires pnpm); npm is the wrong tool",
           "videojs/video.js": "no package-lock.json, so npm ci cannot run (app list error)",
           "nestjs/nest": "npm ci fails with ERESOLVE (peer graphql conflict). Not one of the npm 12 defaults we test; without an npm 11 baseline we cannot say whether npm 11 would also fail"}
apps = []
for r in R:
    a = {"repo": r["repo"], "commit": r.get("commit"), "excluded": EXCLUDE.get(r["repo"])}
    if not a["excluded"]:
        a["ci_ok"] = r["ci_exit"] == 0
        a["ci_error"] = "EALLOWGIT" if "EALLOWGIT" in r.get("ci_log_tail", "") else (None if a["ci_ok"] else "other")
        a["n_blocked"] = r.get("n_blocked")
        a["preexisting_allowScripts"] = r.get("allowScripts_entries") if not r.get("n_blocked") else None
        a["has_build"] = r["has_build"]
        a["build_ok_with_scripts_blocked"] = (r.get("build_exit_blocked") == 0) if r["has_build"] and a["ci_ok"] else None
        a["approve_rebuild_ok"] = (r.get("approve_exit") == 0) if r.get("n_blocked") else None
        name = r["repo"].split("/")[1]
        if name in F:
            f = F[name]
            a["followup_allow_git"] = {"ci_ok": f["ci_exit"] == 0, "n_blocked": f["n_blocked"],
                "note": {"desktop": "install then failed in the app's own postinstall: electron-builder could not find `make` in the sandbox (no build tools installed in the sandbox)",
                         "insomnia": "install then failed while npm ran the git dependency's prepare step (not investigated)"}[name]}
    apps.append(a)
ok = [a for a in apps if not a["excluded"]]
inst = [a for a in ok if a["ci_ok"]]
S = {"apps_listed": len(apps), "excluded": len(apps) - len(ok), "tested": len(ok),
     "ci_failed_eallowgit": sum(1 for a in ok if a["ci_error"] == "EALLOWGIT"),
     "installed": len(inst),
     "installed_with_blocked_scripts": sum(1 for a in inst if a["n_blocked"]),
     "blocked_counts": sorted(a["n_blocked"] for a in inst if a["n_blocked"]),
     "apps_with_preexisting_allowScripts": sum(1 for a in ok if a.get("preexisting_allowScripts")),
     "builds_tried_with_scripts_blocked": sum(1 for a in inst if a["build_ok_with_scripts_blocked"] is not None),
     "builds_ok_with_scripts_blocked": sum(1 for a in inst if a["build_ok_with_scripts_blocked"]),
     "approve_rebuild_ok": sum(1 for a in inst if a["approve_rebuild_ok"]),
     "apps": apps}
json.dump(S, open("data/results/friction-summary.json", "w"), indent=1)
print(json.dumps({k: v for k, v in S.items() if k != "apps"}))
