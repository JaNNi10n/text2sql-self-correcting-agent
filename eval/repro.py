"""Reproducibility check: re-run the first N slice items of an arm and compare with results/<arm>.jsonl.

    python -m eval.repro --arm A0 --n 20   # -> results/repro_<arm>.json

The first attempt is greedy (temperature 0, fixed seed), so the same SQL is expected. Ollama on
GPU is not guaranteed to be bit-exact across runs, so the script reports agreement instead of
asserting it.
"""

from __future__ import annotations

import argparse
import json
import time

from eval.exec_acc import exec_match, run_gold
from t2s.agent import run_agent
from t2s.config import ARMS, RESULTS_DIR, ROOT, SPIDER_DIR, db_path
from t2s.generate import OllamaChat


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="A0", choices=sorted(ARMS))
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args(argv)
    cfg = ARMS[args.arm]
    dev = json.loads((SPIDER_DIR / "dev.json").read_text(encoding="utf-8"))
    items = json.loads((ROOT / "eval" / "slice_ids.json").read_text(encoding="utf-8"))["items"][: args.n]
    old = {}
    for line in (RESULTS_DIR / f"{args.arm}.jsonl").read_text(encoding="utf-8").splitlines():
        if line:
            r = json.loads(line)
            old[r["id"]] = r
    llm = OllamaChat(cfg.model)
    rows = []
    for it in items:
        ex = dev[it["id"]]
        db = str(db_path(ex["db_id"]))
        res = run_agent(ex["question"], db, cfg, llm, db_id=ex["db_id"])
        correct = exec_match(ex["query"], res["sql"], db, run_gold(ex["query"], db))["correct"]
        prev = old[it["id"]]
        rows.append({
            "id": it["id"],
            "same_sql": res["sql"] == prev["pred_sql"],
            "same_correct": correct == prev["correct"],
            "correct_now": correct,
            "correct_before": prev["correct"],
        })
        print(f"id={it['id']:<4} same_sql={rows[-1]['same_sql']} correct {prev['correct']} -> {correct}")
    out = {
        "arm": args.arm,
        "n": len(rows),
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "same_sql": sum(r["same_sql"] for r in rows),
        "same_correctness": sum(r["same_correct"] for r in rows),
        "ex_before": sum(r["correct_before"] for r in rows) / len(rows),
        "ex_now": sum(r["correct_now"] for r in rows) / len(rows),
        "items": rows,
    }
    (RESULTS_DIR / f"repro_{args.arm}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print({k: v for k, v in out.items() if k != "items"})


if __name__ == "__main__":
    main()
