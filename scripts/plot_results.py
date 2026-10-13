"""Plot EX per ablation arm (with Wilson 95% CIs) and per hardness from results/summary.json.

    python scripts/plot_results.py   # -> docs/ex_by_arm.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ["easy", "medium", "hard", "extra"]


def main() -> None:
    arms = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))["arms"]
    names = list(arms)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

    ex = [100 * arms[a]["ex"] for a in names]
    lo = [ex[i] - 100 * arms[a]["ex_ci95"][0] for i, a in enumerate(names)]
    hi = [100 * arms[a]["ex_ci95"][1] - ex[i] for i, a in enumerate(names)]
    bars = ax1.bar(names, ex, yerr=[lo, hi], capsize=5, color="#4C72B0")
    for b, v in zip(bars, ex, strict=True):
        ax1.text(b.get_x() + b.get_width() / 2, 2, f"{v:.1f}", ha="center", color="white", fontsize=10)
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("Execution accuracy (%)")
    ax1.set_title("EX on 200-question Spider-dev slice\n(error bars: Wilson 95% CI)")

    width = 0.8 / len(names)
    for i, a in enumerate(names):
        vals = [100 * arms[a]["per_hardness"][lv]["ex"] for lv in LEVELS]
        xs = [j + (i - (len(names) - 1) / 2) * width for j in range(len(LEVELS))]
        ax2.bar(xs, vals, width, label=a)
    ns = [arms[names[0]]["per_hardness"][lv]["n"] for lv in LEVELS]
    ax2.set_xticks(range(len(LEVELS)), [f"{lv}\n(n={n})" for lv, n in zip(LEVELS, ns, strict=True)])
    ax2.set_ylim(0, 100)
    ax2.set_title("EX by Spider hardness")
    ax2.legend(fontsize=8)
    footer = "qwen2.5-coder:1.5b (*-3b arms: qwen2.5-coder:3b), Q4_K_M via Ollama, RTX 3050 Ti 4 GB"
    fig.text(0.99, 0.01, footer, ha="right", fontsize=7, color="gray")
    fig.tight_layout()
    out = ROOT / "docs" / "ex_by_arm.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
