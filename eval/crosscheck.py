"""Cross-check our EX judgement against the official test-suite-sql-eval `eval_exec_match`.

Takes the first 50 records (slice order) of results/<arm>.jsonl, re-judges each prediction
with the official function on the original Spider DB (plug_value=False, keep_distinct=False,
the official defaults) and reports agreement. Predictions that fail our guard are not
handed to the official script (it would execute them unsandboxed); they count as wrong.

    python -m eval.crosscheck --arm A3
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings

from t2s.config import RESULTS_DIR, ROOT, db_path
from t2s.guard import GuardError, check


def main(arm: str = "A3", n: int = 50) -> dict:
    warnings.filterwarnings("ignore")
    sys.path.insert(0, str(ROOT / "third_party" / "test_suite"))
    from exec_eval import eval_exec_match  # official implementation

    rows = [json.loads(x) for x in (RESULTS_DIR / f"{arm}.jsonl").read_text(encoding="utf-8").splitlines() if x]
    rows = sorted(rows, key=lambda r: r["id"])[:n]
    out, agree = [], 0
    for r in rows:
        try:
            check(r["pred_sql"])
            db = str(db_path(r["db_id"]))
            official = bool(eval_exec_match(db, r["pred_sql"], r["gold_sql"], False, False, False))
        except GuardError:
            official = False
        agree += official == r["correct"]
        out.append({"id": r["id"], "ours": r["correct"], "official": official})
    res = {
        "arm": arm,
        "n": len(rows),
        "agreement": agree / len(rows),
        "ours_ex": sum(r["ours"] for r in out) / len(out),
        "official_ex": sum(r["official"] for r in out) / len(out),
        "disagreements": [
            {**o, "gold": r["gold_sql"], "pred": r["pred_sql"]}
            for o, r in zip(out, rows)
            if o["ours"] != o["official"]
        ],
    }
    (RESULTS_DIR / "crosscheck_official.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "disagreements"}, indent=1))
    print(f"disagreements: {len(res['disagreements'])}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="A3")
    ap.add_argument("--n", type=int, default=50)
    a = ap.parse_args()
    main(a.arm, a.n)
