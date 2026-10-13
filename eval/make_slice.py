"""Build the fixed 200-question Spider-dev slice, stratified by official hardness.

Hardness comes from the official `Evaluator.eval_hardness` (taoyds/test-suite-sql-eval)
applied to the pre-parsed `sql` field of dev.json. Allocation is proportional to the
full-dev hardness distribution (largest-remainder rounding); sampling uses seed 42.

    python -m eval.make_slice            # writes eval/slice_ids.json
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ("easy", "medium", "hard", "extra")


def hardness_labels(dev: list[dict]) -> list[str]:
    sys.path.insert(0, str(ROOT / "third_party" / "test_suite"))
    import nltk

    nltk.data.path.insert(0, str(ROOT / "third_party" / "nltk_data"))
    from evaluation import Evaluator  # official Spider hardness rules

    ev = Evaluator()
    return [ev.eval_hardness(ex["sql"]) for ex in dev]


def allocate(counts: Counter, n: int) -> dict[str, int]:
    total = sum(counts.values())
    raw = {k: n * counts[k] / total for k in LEVELS}
    alloc = {k: int(raw[k]) for k in LEVELS}
    for k in sorted(LEVELS, key=lambda k: raw[k] - alloc[k], reverse=True)[: n - sum(alloc.values())]:
        alloc[k] += 1
    return alloc


def main(n: int = 200, seed: int = 42) -> None:
    dev = json.loads((ROOT / "spider" / "dev.json").read_text(encoding="utf-8"))
    labels = hardness_labels(dev)
    counts = Counter(labels)
    alloc = allocate(counts, n)
    rng = random.Random(seed)
    items = []
    for level in LEVELS:
        pool = [i for i, h in enumerate(labels) if h == level]
        for i in sorted(rng.sample(pool, alloc[level])):
            items.append({"id": i, "db_id": dev[i]["db_id"], "hardness": level})
    items.sort(key=lambda x: x["id"])
    out = {
        "source": "Spider 1.0 dev.json (index = position in file)",
        "seed": seed,
        "n": len(items),
        "full_dev_hardness": {k: counts[k] for k in LEVELS},
        "slice_hardness": alloc,
        "items": items,
    }
    (ROOT / "eval" / "slice_ids.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"full dev: {dict(counts)} -> slice: {alloc}")


if __name__ == "__main__":
    main()
