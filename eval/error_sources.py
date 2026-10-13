"""Where do the "no such table/column" errors come from? Two simple, exact-match checks.

1. Few-shot copying (A2): for each prediction that fails with "no such table/column: X", is X
   (the last dotted part, case-insensitive, whole word) present in the SQL of the retrieved
   example questions? Exact matching undercounts near-copies, so this is a lower bound.
2. Repeated identifiers (A3): for each question that retried after "no such table/column: X"
   and still ends in such an error, is the final missing identifier the same X?

    python -m eval.error_sources   # -> results/error_sources.json
"""

from __future__ import annotations

import json
import re

from t2s.config import RESULTS_DIR, SPIDER_DIR

NO_SUCH = re.compile(r"no such (?:table|column): (\S+)")


def _rows(arm: str) -> list[dict]:
    path = RESULTS_DIR / f"{arm}.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def _missing(err: str | None) -> str | None:
    m = NO_SUCH.search(err or "")
    return m.group(1).split(".")[-1].lower() if m else None


def main() -> None:
    train_sql: dict[str, list[str]] = {}
    for name in ("train_spider.json", "train_others.json"):
        for t in json.loads((SPIDER_DIR / name).read_text(encoding="utf-8")):
            train_sql.setdefault(t["question"], []).append(t["query"])

    errs = copied = 0
    for r in _rows("A2"):
        ident = _missing(r["pred_error"])
        if ident is None:
            continue
        shot_sql = " ".join(q for s in r["shots"] for q in train_sql.get(s, [])).lower()
        errs += 1
        copied += re.search(rf"\b{re.escape(ident)}\b", shot_sql) is not None

    retried = same = 0
    for r in _rows("A3"):
        first = _missing(r["error_trace"][0]["error"]) if r["error_trace"] else None
        final = _missing(r["pred_error"])
        if r["attempts"] > 1 and first and final:
            retried += 1
            same += first == final

    res = {
        "A2_no_such_errors": errs,
        "A2_missing_identifier_in_example_sql": copied,
        "A3_retried_no_such_still_failing_no_such": retried,
        "A3_same_missing_identifier_after_retries": same,
    }
    (RESULTS_DIR / "error_sources.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
