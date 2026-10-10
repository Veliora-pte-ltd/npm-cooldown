"""Check every number in the published note against the results files. No model calls.
Each phrase below is rendered FROM the results files and must appear verbatim in the note.
Run from the repository root:
    python3 method/checks/verify_note.py            # fetches the live note
    python3 method/checks/verify_note.py page.html  # or checks a saved copy"""
import json, re, html, sys, urllib.request
from pathlib import Path
NOTE_URL = "https://veliora.works/engineering/npm-12-cooldown-2026-attacks/"
R = Path(__file__).resolve().parents[2] / "data" / "results"
S = json.loads((R / "summary.json").read_text())
FR = json.loads((R / "friction-summary.json").read_text())
MC = json.loads((R / "manual_codes.json").read_text())
if len(sys.argv) > 1:
    page = Path(sys.argv[1]).read_text()
else:
    req = urllib.request.Request(NOTE_URL, headers={"User-Agent": "npm-cooldown-verify/1.0"})
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
T = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)))
T = re.sub(r" ([,.;:)])", r"\1", T).replace("( ", "(")
T += " " + " ".join(html.unescape(a) for a in re.findall(r'alt="([^"]*)"', page))  # chart alt texts
PL = None  # the plain-text export is not part of this repository
r = lambda x: round(x * 100)
pc = lambda x: f"{r(x)}%"
ci = lambda w: f"{r(w[0])}%–{r(w[1])}%"
n_ = lambda x: f"{x:,}"
d1 = lambda x: f"{x:.1f}"
C, P, H, F = S["cooldown"], S["population"], S["hijack"], S["fix_delay"]
top = F["top1000"]
sh = lambda k, N: C[N]["removal_simple"]
camp = S["campaigns"]
checks = {}
def need(label, phrase, also_plain=True):
    spoken = re.sub(r"(\d+%)–(\d+%)", r"\1 to \2", phrase).replace("–", " to ")  # plain text spells ranges out
    checks[label] = (phrase, phrase in T, (PL is None or not also_plain) or spoken in PL)

# population
need("records 12,856", f"{n_(P['mal_published_2026'])} records, of which {P['withdrawn']} were withdrawn", False)
need("12,693 records in 12,692 packages", f"{n_(P['analysed'])} records in {n_(P['packages'])} packages")
need("whole package 6,619", f"({n_(P['whole_package_range'])})")
need("packuments 12,692", f"all {n_(P['packages'])} affected packages", False)
# cooldown
for N, lab in (("1h", "1 hour"), ("1d", "1 day"), ("3d", "3 days"), ("7d", "7 days"), ("14d", "14 days")):
    need(f"table removal {N}", f"{lab} {pc(sh(0, N)['share'])} ({ci(sh(0, N)['wilson'])}) {pc(C[N]['flag_or_removal_km_stopped'])} {pc(H['flag_or_removal']['stopped'][N]['share'])}", False)
need("tldr 7d 67 (66-68)", f"skipped {pc(sh(0,'7d')['share'])} (95% interval {ci(sh(0,'7d')['wilson'])})")
need("tldr 1d 53", f"would have skipped {pc(sh(0,'1d')['share'])}. One in three")
need("one in three after a week", "One in three was still installable after a week") ; assert 0.30 < 1 - C["7d"]["removal_km_stopped"] < 0.37
need("median removal 10.8h", f"removed {d1(S['timing']['removed_known_hours']['median'])} hours after publication")
need("p25 ~5 min", "a quarter were gone within about five minutes"); assert 4 <= S["timing"]["removed_known_hours"]["p25"] * 60 <= 6
need("p75 13 days", "a quarter were still up after 13 days"); assert round(S["timing"]["removed_known_hours"]["p75"] / 24) == 13
need("1->7 adds 14", f"Going from one day to seven adds {r(sh(0,'7d')['share']) - r(sh(0,'1d')['share'])} points")
need("7->14 adds 4", f"going from seven to fourteen adds {['zero','one','two','three','four','five'][r(sh(0,'14d')['share']) - r(sh(0,'7d')['share'])]} more")
st = S["still_listed"]
need("still listed 675", f"{n_(st['records'])} releases that OSV has flagged as malicious are still listed")
need("still 6%", f"{pc(st['share_of_usable']['share'])} of the releases with usable timing")
need("still median 84 days", f"listed for {round(st['median_days_listed'])} days")
need("tldr 675", f"{n_(st['records'])} flagged releases are still on the registry today")
need("usable 11,073", f"{n_(S['timing']['usable']['k'])} records with a publication time")
# npm 12
m = S["npm12"]
need("stated 5,822 of 12,693 (46%)", f"{n_(m['stated_vector']['k'])} of the {n_(P['analysed'])} advisories ({pc(m['stated_vector']['share'])})")
need("install only 3,089 (53%, 52-54)", f"{n_(m['install_only_of_stated']['k'])} ({pc(m['install_only_of_stated']['share'])}, 95% interval {ci(m['install_only_of_stated']['wilson'])})")
need("install plus 639", f"Another {m['classes']['install_plus']} use an install script plus another route")
need("no install 2,094", f"{n_(m['classes']['no_install'])} don't use install scripts at all")
need("24% of all", f"at least {pc(m['install_only_of_all']['share'])} would have been stopped by npm 12 alone")
need("6,871 silent", f"the {n_(m['classes']['unknown'])} silent records")
need("tldr 53% install only", f"{pc(m['install_only_of_stated']['share'])} of the releases whose advisory says how the code runs")
need("tldr 54% don't say", f"Most advisories ({pc(1 - m['stated_vector']['share'])}) don't say")
v = S["validation"]
need("validation 51/60 53/60", f"on {v['labelled_n']} records it had labelled. It matched my reading exactly on {v['exact']['k']} and agreed on the question that matters here (install script only, or not) on {v['npm12_binary']['k']}")
need("unclear 28/30, 0 missed", f"I also read {v['unclear_n']} records it called unclear. In {v['unclear_n'] - v['unclear_with_stated_vector']['k']} the advisory really doesn't say"); assert v["unclear_missed_install_script"] == 0
need("limitations 51/60 53/60", f"({v['exact']['k']} of {v['labelled_n']} exact matches; {v['npm12_binary']['k']} of {v['labelled_n']} on the npm 12 question)")
# matrix
mx = S["matrix"]["7d"]
need("matrix 30/19/36/15", f"{pc(mx['both']['share'])} would have been stopped by both, {pc(mx['scripts_only']['share'])} only by npm 12, {pc(mx['cooldown_only']['share'])} only by the cooldown and {pc(mx['neither']['share'])} by neither")
need("tldr combined 85", f"would have stopped {pc(1 - mx['neither']['share'])}. {pc(mx['neither']['share'])} would have got through both")
ea = S["either_all_conservative"]
need("conservative 76 / 64", f"a seven-day cooldown plus npm 12 stops {pc(ea['7d']['share'])}, and a one-day cooldown plus npm 12 stops {pc(ea['1d']['share'])}")
# hijack
need("hijack 1,063", f"That gives {n_(H['records'])} records")
need("hijack 733 hand coded", f"Six campaigns account for {H['hand_coded_records']} of them"); assert len(MC["campaigns"]) == 6
iost = H["install_only_of_stated_hand"]
need("hijack 824 of 854 96% (95-98)", f"Of the {iost['n']} hijacked-package releases whose execution path is known, {iost['k']} ({pc(iost['share'])}, 95% interval {ci(iost['wilson'])})")
need("tldr hijack 1,063 / 96%", f"of {n_(H['records'])} malicious releases of established packages")
need("tldr hijack 96 pct", f"{pc(iost['share'])} of those with a known execution path")
need("tldr hijack 97% 7d", f"{pc(H['flag_or_removal']['stopped']['7d']['share'])} of them were flagged or removed within seven days")
mh7, mh1 = H["matrix_7d_flag_hand"], H["matrix_1d_flag_hand"]
need("tldr only 4 of 854", f"Only {mh7['neither']['k']} of {mh7['n']} got past both")
need("hijack median 3.7h", f"The median was {d1(H['flag_or_removal']['median_hours'])} hours from publication")
need("hijack 87/97", f"{pc(H['flag_or_removal']['stopped']['1d']['share'])} were flagged or removed within a day and {pc(H['flag_or_removal']['stopped']['7d']['share'])} within seven")
need("hijack 4 of 854, 12 at 1 day", f"Only {mh7['neither']['k']} of the {mh7['n']} would have got past both npm 12 and a seven-day cooldown, and {mh1['neither']['k']} past npm 12 plus a one-day cooldown")
need("hijack removal lower bound 43", f"a seven-day cooldown stops at least {pc(H['cooldown']['7d']['removal_simple']['share'])}")
need("limitations lower bound 43", f"Removal alone gives a lower bound of {pc(H['cooldown']['7d']['removal_simple']['share'])} at seven days")
need("483 of 495", f"{H['t_gone_source_of_removed_known']['time.modified']} of the {H['removed_known_hours']['n']} recorded removal times")
need("1h hijack 8%", f"only {pc(S['pnpm_claim']['hijack_flag_or_removal_within_1h']['share'])} had even been flagged within an hour")
for key, recs, hrs, d in (("shai_hulud_aug", None, None, None), ("mini_shai_hulud_atool", None, None, None), ("mini_shai_hulud_back", None, None, None), ("mini_shai_hulud_redhat", None, None, None)):
    c = camp[key]; s1 = c["stopped_1d_flag_or_removal"]["share"] * 100
    s1t = f"{s1:.1f}%" if s1 < 99.95 else "100%"
    need(f"campaign {key}", f"{c['records']} {c['code'] and ''}".strip() and f"{d1(c['median_hours_to_flag_or_removal'])} {s1t}", False)
    need(f"campaign {key} records", f"{c['records']} ", False)
need("miasma 20, SAP 4", f"Miasma worm on {camp['miasma_leo']['records']} LeoPlatform packages")
need("sap 4", f"{['zero','one','two','three','four'][camp['sap_cap']['records']]} SAP CAP packages")
# pnpm claim
pc_ = S["pnpm_claim"]
need("pnpm 29% (28-30), 31% excl", f"In this data, {pc(pc_['removed_within_1h_simple']['share'])} were (95% interval {ci(pc_['removed_within_1h_simple']['wilson'])}; {pc(pc_['removed_within_1h_excl_time_modified']['share'])} if removal times")
need("tldr pnpm 29", f"Here, {pc(pc_['removed_within_1h_simple']['share'])} were")
# fix delay
need("761 rows", f"{top['units']} advisory rows in the 1,000")
need("fix before advisory 96%", f"{pc(top['fix_before_advisory']['share'])} of fixes in the top 1,000 packages were published before")
for N, lab in (("1d", "1 day"), ("3d", "3 days"), ("7d", "7 days"), ("14d", "14 days")):
    t = top[N]
    need(f"fix table {N}", f"{lab} {pc(t['zero_extra']['share'])} {pc(t['over_3_days']['share'])} {d1(t['mean'])} days {d1(t['median_if_delayed'])} days", False)
need("tldr fix 51 / 2.5 / 38 / 0.2", f"you would have got {pc(top['7d']['zero_extra']['share'])} of security fixes")
need("tldr mean 2.5", f"On average fixes arrived {d1(top['7d']['mean'])} days later, and {pc(top['7d']['over_3_days']['share'])} arrived more than three days late. A one-day cooldown cost an average of {d1(top['1d']['mean'])} days")
cc = F["top1000_concentration"]
need("electron+next 254", f"Electron and Next.js account for {cc['largest'][0][1] + cc['largest'][1][1]} of the {top['units']} rows"); assert [x[0] for x in cc["largest"][:2]] == ["electron", "next"]
need("package weighted 41 / excl 47", f"falls to {pc(cc['package_weighted_zero_extra']['7d'])}. Without those two packages it is {pc(cc['excluding_largest_two']['7d']['zero_extra']['share'])}")
need("all 4,181 47% 2.5, crit/high 47", f"Across all {n_(F['all']['units'])} npm advisory rows with a fix, the seven-day figure is {pc(F['all']['7d']['zero_extra']['share'])} with a mean of {d1(F['all']['7d']['mean'])} days, and the same holds for critical and high severity alone ({pc(F['all_critical_high']['7d']['zero_extra']['share'])})")
need("4,442 rows", f"{n_(F['units_total'])} GitHub-reviewed npm advisory rows", False)
need("advice 1-3 days", f"({pc(sh(0,'1d')['share'])} to {pc(sh(0,'3d')['share'])} of all malicious releases removed in time, and {pc(H['flag_or_removal']['stopped']['1d']['share'])} to {pc(H['flag_or_removal']['stopped']['3d']['share'])} of hijacks")
need("advice 7d 2.5", f"at a cost of {d1(top['7d']['mean'])} days on average")
# limitations / sensitivity
need("August 4,078", f"August alone has {n_(P['by_month']['2026-08'])} records")
bm = {k: v["share"] for k, v in S["by_month_7d"].items()}
need("month range 49 May 83 Jan", f"ranges from {pc(min(bm.values()))} (May) to {pc(max(bm.values()))} (January)"); assert min(bm, key=bm.get) == "2026-05" and max(bm, key=bm.get) == "2026-01"
tg = S["timing"]["t_gone_source"]
need("unpublish 3,222 / security 6,537 / modified 639", f"({n_(tg['unpublished.time'])} records) and the <code>-security</code> placeholder time otherwise ({n_(tg['security-holding'])})".replace("<code>", "").replace("</code>", ""))
need("modified 639", f"For {tg['time.modified']} records the only signal")
need("unknown 672, none 948", f"{tg['removed-time-unknown']} removed releases, and {S['timing']['classes']['no_publish_time']} records had no registry metadata")
sv = [S["sensitivity"][k]["7d"]["share"] for k in S["sensitivity"] if S["sensitivity"][k]] + [sh(0, "7d")["share"]]
need("sensitivity 58-69", f"the seven-day figure ranges from {pc(min(sv))} to {pc(max(sv))}")
need("date-only 823", f"{S['timing']['classes']['_flag_date_only_published']} OSV records carry a date-only")
need("clipped 205", f"{C['flag_before_publish_clipped']} records were flagged before")
# friction
need("friction 7 usable", f"{FR['tested']} usable apps")
need("friction 3 excluded", f"{['Zero','One','Two','Three'][FR['excluded']]} could not be tested")
need("friction two EALLOWGIT", f"{['Zero','One','Two','Three'][FR['ci_failed_eallowgit']]} failed at once")
bc = {a["repo"]: a.get("n_blocked") for a in FR["apps"]}
need("friction blocked counts", f"Bitwarden ({bc['bitwarden/clients']} packages), LibreChat ({bc['danny-avila/LibreChat']}), Parse Server ({bc['parse-community/parse-server']}) and Jellyfin Web ({bc['jellyfin/jellyfin-web']})")
fu = [a for a in FR["apps"] if a["repo"] == "mattermost/desktop"][0]["followup_allow_git"]["n_blocked"]
need("desktop 7 after allow-git", f"Mattermost Desktop had {fu} more")
pre = {a["repo"]: a.get("preexisting_allowScripts") for a in FR["apps"]}
need("allowScripts 17 / 9", f"Uptime Kuma ({pre['louislam/uptime-kuma']} entries) and Insomnia ({pre['Kong/insomnia']})")
need("builds 3/3", f"all {['zero','one','two','three'][FR['builds_ok_with_scripts_blocked']]} apps with a top-level build script built successfully"); assert FR["builds_ok_with_scripts_blocked"] == FR["builds_tried_with_scripts_blocked"]
need("approve 4/4", f"worked for all {['zero','one','two','three','four'][FR['approve_rebuild_ok']]} apps"); assert FR["approve_rebuild_ok"] == FR["installed_with_blocked_scripts"]
need("ten apps", "I installed ten open-source apps"); assert FR["apps_listed"] == 10

# chart alt text (exposure curve) and other figures
k = S["km_curve"]; g = k["hours"]
at = lambda key, h: pc(k[key][g.index(h)])
need("alt: all removal 1h/1d/7d", f"about {at('removal',1)} after 1 hour, {at('removal',24)} after 1 day and {at('removal',168)} after 7 days", False)
need("alt: flag 1d/7d", f"{at('flag_or_removal',24)} after 1 day and {at('flag_or_removal',168)} after 7 days", False)
need("alt: hijack 1d/7d", f"{at('hijack_flag_or_removal',24)} after 1 day and {at('hijack_flag_or_removal',168)} after 7 days", False)
assert k["hijack_flag_or_removal"][g.index(3)] > 0.75 and k["hijack_flag_or_removal"][g.index(6)] < 0.75
rows_n = [C[N]["removal_simple"]["n"] for N in ("1h", "1d", "3d", "7d", "14d")]
need("about 11,060 per row", "about 11,060 records per row", False); assert all(abs(x - 11060) < 25 for x in rows_n)
assert "3,006.8 h (about 125 days)" in MC["validation_of_removal_times"]["antv_attr"]
need("125 days", "shows 125 days")
cd = (R / "cooldown-check.txt").read_text()
for ph in ("8.3.2", "8.3.3", "8.3.4"): assert ph in cd
need("vite check", "resolved vite to 8.3.2 instead of that day's 8.3.4", False)

bad = [k for k, (ph, ok, okp) in checks.items() if not ok]
badp = [k for k, (ph, ok, okp) in checks.items() if not okp]
print(f"phrases in page: {len(checks) - len(bad)} / {len(checks)}")
for k in bad: print("  MISSING (page):", k, "->", repr(checks[k][0]))
if PL is not None:
    print(f"phrases in plain text: {len(checks) - len(badp)} / {len(checks)}")
    for k in badp: print("  MISSING (plain):", k, "->", repr(checks[k][0]))
sys.exit(1 if bad or badp else 0)
