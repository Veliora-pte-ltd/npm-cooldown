#!/usr/bin/env python3
"""Article charts, in the house style of Engineering notes article 1 (Figtree, paper background,
bold titles, source line). Reads data/results/summary.json only. Writes data/charts/<name>.png (2600 px wide)
plus <name>-2600.webp and <name>-1300.webp."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "charts"
for f in (OUT / "fonts").glob("*.ttf"):
    font_manager.fontManager.addfont(str(f))
NAVY, TEAL, TEAL_DARK, PAPER, INK, MUTED, LINE = "#081426", "#49c7ba", "#0f6f68", "#f5f3ee", "#0b1629", "#46566a", "#d6d2c8"
RED, GREY = "#c0472a", "#c3ccd4"
plt.rcParams.update({"font.family": "Figtree", "font.size": 15, "axes.edgecolor": INK, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": MUTED, "figure.facecolor": PAPER, "axes.facecolor": PAPER,
                     "savefig.facecolor": PAPER})
S = json.loads((ROOT / "data" / "results" / "summary.json").read_text())
SRC = "Source: Veliora Engineering notes, 8 October 2026."


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    png = OUT / f"{name}.png"
    fig.savefig(png, dpi=200)
    plt.close(fig)
    im = Image.open(png).convert("RGB")
    im.save(OUT / f"{name}-2600.webp", "WEBP", quality=88, method=6)
    w, h = im.size
    im.resize((1300, round(h * 1300 / w)), Image.LANCZOS).save(OUT / f"{name}-1300.webp", "WEBP", quality=88, method=6)


def style(ax, grid="y"):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(INK)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis=grid, color=LINE, linewidth=1)
    ax.set_axisbelow(True)


def exposure():
    k = S["km_curve"]; hrs = k["hours"]
    fig, ax = plt.subplots(figsize=(13, 7.6))
    style(ax)
    series = [("removal", "All 2026 malicious releases: until removed from the registry", NAVY, "-", 3.4),
              ("flag_or_removal", "All: until removed or publicly flagged, whichever came first", TEAL, "--", 3.0),
              ("hijack_flag_or_removal", "Hijacked established packages: until removed or flagged", RED, "-", 3.4)]
    for key, lab, col, ls, lw in series:
        ys = [v * 100 for v in k[key]]
        ax.plot(hrs, ys, color=col, linestyle=ls, linewidth=lw, label=lab, zorder=3)
    ax.set_xscale("log")
    ticks = [0.25, 1, 6, 24, 72, 168, 336, 720]
    ax.set_xticks(ticks, ["15 min", "1 hour", "6 hours", "1 day", "3 days", "7 days", "14 days", "30 days"], fontsize=13)
    ax.minorticks_off()
    ax.set_ylim(0, 105)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"], fontsize=13)
    for h, t in ((24, "1-day cooldown"), (168, "7-day cooldown")):
        ax.axvline(h, color=INK, linewidth=1.4, linestyle=":", zorder=2)
        ax.text(h * 1.06, 101, t, fontsize=12.5, color=INK, fontweight=600, va="top")
    r7 = S["cooldown"]["7d"]["removal_km_stopped"]
    ax.annotate(f"{(1 - r7) * 100:.0f}% still installable\nafter 7 days", xy=(168, (1 - r7) * 100), xytext=(40, 62), ha="left",
                fontsize=13, fontweight=800, color=NAVY, arrowprops=dict(arrowstyle="-", color=NAVY, lw=1.4))
    ax.set_xlim(0.25, 720)
    fig.suptitle("How long malicious npm releases stayed installable", x=0.012, y=0.985, ha="left", fontsize=24, fontweight=800, color=INK)
    fig.text(0.012, 0.905, "Share still available, by time since publication (12,693 OSV malicious-package records, 2026)", fontsize=15, color=MUTED)
    fig.legend(loc="upper left", bbox_to_anchor=(0.005, 0.875), frameon=False, fontsize=13.5, ncol=1, handlelength=2.6)
    n_all = S["timing"]["usable"]["k"]; n_hj = S["hijack"]["flag_or_removal"]["n"]
    fig.text(0.012, 0.012, f"{SRC} Kaplan–Meier estimates. All releases: n = {n_all:,} with a publish time and a removal time or still listed.\n"
             f"Hijacked established packages: n = {n_hj:,}; registry removal times are unreliable for these, so the flag time is used (see Methods).",
             fontsize=10.5, color=MUTED, linespacing=1.4)
    fig.subplots_adjust(left=0.06, right=0.975, top=0.68, bottom=0.15)
    save(fig, "npm-exposure")


def stopped():
    cats = [("both", "Both", NAVY), ("scripts_only", "npm 12 script blocking only", TEAL),
            ("cooldown_only", "7-day cooldown only", TEAL_DARK), ("neither", "Neither", RED)]
    rows = [("All 2026 malicious releases\nthat state how they run", S["matrix"]["7d"]),
            ("Hijacked established\npackages", S["hijack"]["matrix_7d_flag_hand"])]
    fig, ax = plt.subplots(figsize=(13, 6.4))
    for s_ in ("top", "right", "left", "bottom"):
        ax.spines[s_].set_visible(False)
    ax.tick_params(length=0)
    for i, (lab, m) in enumerate(rows):
        y = len(rows) - 1 - i; left = 0
        for key, name, col in cats:
            v = m[key]["share"] * 100
            ax.barh(y, v, left=left, color=col, height=0.58, edgecolor=PAPER, linewidth=2)
            if v >= 6:
                ax.text(left + v / 2, y, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=15, fontweight=800)
            elif v >= 1.5:
                ax.text(left + v / 2, y - 0.42, f"{v:.0f}%", ha="center", va="center", color=INK, fontsize=12, fontweight=800)
            left += v
        ax.text(-1, y, lab, ha="right", va="center", fontsize=14.5, fontweight=800, color=INK)
        ax.text(101, y, f"n = {m['n']:,}", ha="left", va="center", fontsize=12.5, color=MUTED)
    ax.set_xlim(0, 100); ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Which defence would have stopped them", x=0.012, y=0.985, ha="left", fontsize=24, fontweight=800, color=INK)
    fig.text(0.012, 0.885, "npm 12's default block on dependency install scripts, and a 7-day minimum release age", fontsize=15, color=MUTED)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in cats]
    fig.legend(handles, [n for _, n, _ in cats], loc="upper left", bbox_to_anchor=(0.005, 0.85), frameon=False, fontsize=13.5, ncol=4)
    fig.text(0.012, 0.012, f"{SRC} Top bar: records whose advisory states the execution path and whose 7-day outcome is known; a release counts\n"
             "as stopped by the cooldown if npm removed it within 7 days. Bottom bar: removed or publicly flagged within 7 days; campaign vectors hand-coded.",
             fontsize=10.5, color=MUTED, linespacing=1.4)
    fig.subplots_adjust(left=0.25, right=0.93, top=0.7, bottom=0.17)
    save(fig, "npm-stopped")


def fixdelay():
    f = S["fix_delay"]["top1000"]
    Ns = ["1d", "3d", "7d", "14d"]; labs = ["1 day", "3 days", "7 days", "14 days"]
    fig, ax = plt.subplots(figsize=(13, 7.2))
    style(ax)
    for i, n in enumerate(Ns):
        z = f[n]["zero_extra"]["share"] * 100; o3 = f[n]["over_3_days"]["share"] * 100; mid = 100 - z - o3
        ax.bar(i, z, 0.62, color=TEAL, zorder=2)
        ax.bar(i, mid, 0.62, bottom=z, color=GREY, zorder=2)
        ax.bar(i, o3, 0.62, bottom=z + mid, color=RED, zorder=2)
        ax.text(i, z / 2, f"{z:.0f}%", ha="center", va="center", color=INK, fontsize=16, fontweight=800)
        if o3 >= 6:
            ax.text(i, z + mid + o3 / 2, f"{o3:.0f}%", ha="center", va="center", color="white", fontsize=16, fontweight=800)
        ax.text(i, 103, f"mean +{f[n]['mean']:.1f} days", ha="center", va="bottom", fontsize=13, color=INK, fontweight=800)
    ax.set_xticks(range(4), labs, fontsize=14.5, fontweight=600)
    ax.set_xlabel("Cooldown length", fontsize=14, color=MUTED, labelpad=8)
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"], fontsize=13)
    fig.suptitle("What a cooldown costs: later security fixes", x=0.012, y=0.985, ha="left", fontsize=24, fontweight=800, color=INK)
    fig.text(0.012, 0.905, f"Extra wait for the first fixed version after the advisory, {f['units']} fixes in the 1,000 most-depended-on npm packages", fontsize=15, color=MUTED)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (TEAL, GREY, RED)]
    fig.legend(handles, ["No extra wait", "Up to 3 days later", "More than 3 days later"], loc="upper left",
               bbox_to_anchor=(0.005, 0.875), frameon=False, fontsize=13.5, ncol=3)
    fig.text(0.012, 0.012, f"{SRC} GitHub-reviewed npm advisories published 1 October 2025 to 30 September 2026, one row per advisory, package\n"
             "and fixed version. Extra wait = max(0, fix publish time + cooldown − later of advisory time and fix publish time).",
             fontsize=10.5, color=MUTED, linespacing=1.4)
    fig.subplots_adjust(left=0.06, right=0.985, top=0.74, bottom=0.18)
    save(fig, "npm-fix-delay")


exposure(); stopped(); fixdelay()
