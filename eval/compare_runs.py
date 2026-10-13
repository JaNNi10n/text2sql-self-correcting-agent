"""Compare two full runs of the same arm (per-question JSONL files) question by question.

    python -m eval.compare_runs results/A3.jsonl results/rerun/A3.jsonl --out results/rerun/compare_A3.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scipy.stats import binomtest


def _load(p: Path) -> dict[int, dict]:
    return {r["id"]: r for r in map(json.loads, p.read_text(encoding="utf-8").splitlines()) if r}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    a, b = _load(args.before), _load(args.after)
    ids = sorted(a.keys() & b.keys())
    gained = sum(1 for i in ids if not a[i]["correct"] and b[i]["correct"])
    lost = sum(1 for i in ids if a[i]["correct"] and not b[i]["correct"])
    res = {
        "before": args.before.as_posix(),
        "after": args.after.as_posix(),
        "n": len(ids),
        "ex_before": round(100 * sum(a[i]["correct"] for i in ids) / len(ids), 1),
        "ex_after": round(100 * sum(b[i]["correct"] for i in ids) / len(ids), 1),
        "same_final_sql": sum(a[i]["pred_sql"] == b[i]["pred_sql"] for i in ids),
        "same_correctness": sum(a[i]["correct"] == b[i]["correct"] for i in ids),
        "wrong_to_right": gained,
        "right_to_wrong": lost,
        "mcnemar_p": round(binomtest(gained, gained + lost, 0.5).pvalue, 4) if gained + lost else 1.0,
    }
    args.out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
