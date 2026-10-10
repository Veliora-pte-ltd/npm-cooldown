# Pre-registration: would npm 12's defaults and a cooldown have stopped 2026's npm attacks, and what do they cost?

Written Thursday 8 October 2026, ~18:15 BST, after a feasibility pilot and before the
full timing pass, the fix-delay run and the friction run were analysed. The pilot numbers were seen.
The internal study plan it refers to (approved on 8 October 2026, with the app run trimmed to 10 apps) is not published.

> Edited for publication on 10 October 2026: references to internal files and people were removed and
> file paths were updated to this repository's layout. The definitions, the questions and Amendment 1 are unchanged.

## Data snapshot
OSV npm dump `all.zip`, 218,037,964 bytes, last-modified 2026-10-08 16:48:22 UTC (sha256 in
`data/osv-npm-all.zip.sha256`). Registry packuments fetched on 8 October 2026 (cached, trimmed, in
`data/packuments.jsonl`). Population: MAL- records with OSV `published` in 2026, minus OSV-withdrawn records.

## Questions
RQ1–RQ6, summarised from the internal plan:
- **RQ1, script blocking.** Of the 2026 npm malicious-package records, what share had a clear execution vector? Of those, what share ran only through an install-time lifecycle script (`preinstall`/`install`/`postinstall`/`binding.gyp`), which npm 12's default `allowScripts` deny would have stopped at install?
- **RQ2, cooldowns.** What share of malicious versions were removed from the registry (or publicly flagged) before they were 1, 3, 7 or 14 days old?
- **RQ3, combined.** What share is stopped by blocking only, by a cooldown only, by both, or by neither?
- **RQ4, high-impact subset.** RQ1–3 restricted to hijacked established packages.
- **RQ5, cost to patch speed.** For the ~1,000 most-depended-on packages, how many extra days does a 1/3/7/14-day cooldown add before a security fix can be installed?
- **RQ6, cost of script blocking (secondary).** On ~10–20 real open-source apps, what needs `allowScripts` approval under npm 12, and what breaks if nothing is approved?
- **Claim check.** pnpm's docs say: "In most cases, malicious releases are discovered and removed from the registry within an hour." RQ2/RQ4 test this on 2026 data.

## Definitions
- `t_pub`: registry publish time of the earliest affected version (`time[version]`); for whole-package
  records with no version time, `time.created`.
- `t_gone`: `time.unpublished.time`; else publish time of the npm `-security` holding version; else
  `time.modified` when the affected versions are no longer listed and nothing was published after them.
- `t_flag`: earliest of OSV `published` and the source origins' `modified_time`.
- **Change from the plan, made before analysis:** the primary end of exposure is `t_gone` (removal), not
  min(`t_gone`, `t_flag`). Reason: a cooldown only protects you if the version is gone when the window
  ends; a flagged version that is still installable is still resolved by npm. min(`t_gone`, `t_flag`) is
  reported as a secondary, optimistic scenario ("your tooling also refuses flagged versions").
- Still-listed versions are right-censored at the snapshot time. Records with no recoverable removal time
  (packument 404, or removed with later publishes) are excluded from removal-time shares and counted.
- A cooldown of N days stops a version if `t_gone − t_pub < N days` (N = 1, 3, 7, 14).
- **Hijacked established package (RQ4):** OSV lists specific affected versions (not the whole package),
  the package had at least 5 earlier versions, and its first earlier version was published at least
  90 days before the first malicious version.
- Execution vector: rules in `method/scripts/osv_census.py` (v3, negation-aware) over summary and details.
  npm 12 script blocking "stops" a record only if its stated vector is install scripts and nothing else.
  Records with no stated vector are reported as unknown, never assumed either way.
- Hand validation: the 30 records coded in the pilot plus a further 30 rule-labelled and 30 "unclear"
  records drawn at random (seed 20261008). Every hijack-subset campaign cluster (records grouped by
  identical advisory text) is coded by hand, using advisory text and, where cited, vendor write-ups.
  (The plan said 300 + hijack subset; trimmed to 90 for speed. Stated in limitations.)

## RQ5
Unit: (GHSA advisory, package, first fixed version), npm GHSA records published 2025-10-01 to
2026-09-30, not withdrawn. `t_adv` = earliest of OSV `published`, `github_reviewed_at`,
`nvd_published_at`. Extra delay(N) = max(0, (t_fix + N) − max(t_adv, t_fix)). Primary set: packages in
the top 1,000 by dependent packages (ecosyste.ms, fetched 8 October 2026). Secondary: all packages.

## RQ6 (secondary, does not block publication)
10 apps in `data/friction-apps.json`, npm 12.2.0 on Node 24.21.0, each in a bubblewrap sandbox with a
cleared environment. Measures: `npm ci` success, packages with blocked install scripts, build success
before and after approving all scripts. No npm 11 baseline run (the "approve all" state stands in for
the old behaviour); tests not run (time).

## Analysis
Shares with Wilson 95% intervals. Kaplan–Meier for time to removal. No outcome is preferred; every
scenario is reported.

## Amendment 1 (Thursday 8 October 2026, ~18:45 BST, after the first full analysis run)
For hijacked established packages (RQ4), 483 of the 495 records with a removal time get it from the
`time.modified` fallback, and spot checks show that fallback can be months late for such packages
(@antv/attr: 125 days by `time.modified`, against an OSV record published within minutes; TanStack's
postmortem gives npm removal 2.9 to 4.6 hours after publish, while our packuments give no removal time).
Established packages receive later metadata edits, so `time.modified` is only an upper bound on removal.
Therefore, for RQ4 only, the headline estimate uses min(`t_gone`, `t_flag`), and the removal-only figure is
reported as a lower bound on what a cooldown would have stopped. This was decided after seeing the data.
Added sensitivity checks for the whole population: excluding `time.modified` removals, and keeping only
records whose publish time comes from `time[version]`. Campaign-level hand codes are in
`data/results/manual_codes.json`.
