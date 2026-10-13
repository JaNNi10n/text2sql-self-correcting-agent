"""Categorise failed predictions of one arm with simple, transparent rules.

Rules are applied in order; the first that fires wins:
  1. schema hallucination - prediction errors with "no such table/column"
  2. wrong join           - prediction uses a different set of tables than the gold SQL
  3. wrong aggregation    - different aggregate functions or GROUP BY / HAVING usage
  4. value mismatch       - different literal values in filters
  5. other                - same tables/aggregates/values, but wrong projection, ordering,
                            limit, set operation or nesting
The 10 shown cases are picked round-robin across categories (lowest question id first).

    python -m eval.failures --arm A3   # -> results/failure_cases.md, results/failure_categories.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

import sqlglot
from sqlglot import exp

from t2s.config import RESULTS_DIR

CATS = ["schema hallucination", "wrong join", "wrong aggregation", "value mismatch", "other"]
AGGS = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)


def _features(sql: str) -> dict | None:
    try:
        t = sqlglot.parse_one(sql, read="sqlite")
    except sqlglot.errors.SqlglotError:
        return None
    return {
        "tables": {x.name.lower() for x in t.find_all(exp.Table)},
        "aggs": Counter(type(a).__name__ for a in t.find_all(*AGGS)),
        "group": bool(list(t.find_all(exp.Group))),
        "having": bool(list(t.find_all(exp.Having))),
        "values": {str(v.this).lower().strip("%") for v in t.find_all(exp.Literal)},
    }


def categorise(rec: dict) -> str:
    err = (rec.get("pred_error") or "").lower()
    if "no such table" in err or "no such column" in err:
        return "schema hallucination"
    g, p = _features(rec["gold_sql"]), _features(rec["pred_sql"])
    if g is None or p is None:
        return "other"
    if g["tables"] != p["tables"]:
        return "wrong join"
    if g["aggs"] != p["aggs"] or g["group"] != p["group"] or g["having"] != p["having"]:
        return "wrong aggregation"
    if g["values"] != p["values"]:
        return "value mismatch"
    return "other"


def main(arm: str = "A3", k: int = 10) -> dict:
    rows = [json.loads(x) for x in (RESULTS_DIR / f"{arm}.jsonl").read_text(encoding="utf-8").splitlines() if x]
    failed = sorted((r for r in rows if not r["correct"]), key=lambda r: r["id"])
    for r in failed:
        r["category"] = categorise(r)
    counts = Counter(r["category"] for r in failed)
    buckets = {c: [r for r in failed if r["category"] == c] for c in CATS}
    picked: list[dict] = []
    while len(picked) < k and any(buckets.values()):
        for c in CATS:
            if buckets[c] and len(picked) < k:
                picked.append(buckets[c].pop(0))
    md = [f"# Failure cases ({arm})", "",
          f"{len(failed)} of {len(rows)} slice questions were answered incorrectly. Rule-based categories "
          "(see `eval/failures.py`):", "", "| Category | Count |", "|---|---|"]
    md += [f"| {c} | {counts.get(c, 0)} |" for c in CATS]
    md += ["", "## 10 examples", ""]
    for r in picked:
        md += [f"### #{r['id']} ({r['db_id']}, {r['hardness']}) - {r['category']}", "",
               f"**Question:** {r['question']}", "",
               f"Gold: `{r['gold_sql']}`", "", f"Predicted: `{r['pred_sql']}`", ""]
        if r.get("pred_error"):
            md += [f"Error: `{r['pred_error']}`", ""]
    (RESULTS_DIR / "failure_cases.md").write_text("\n".join(md), encoding="utf-8")
    res = {"arm": arm, "failed": len(failed), "counts": {c: counts.get(c, 0) for c in CATS},
           "examples": [{k2: r[k2] for k2 in ("id", "category", "question", "gold_sql", "pred_sql")} for r in picked]}
    (RESULTS_DIR / "failure_categories.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res["counts"]))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="A3")
    a = ap.parse_args()
    main(a.arm)
