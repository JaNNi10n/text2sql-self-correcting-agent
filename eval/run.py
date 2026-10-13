"""Run one ablation arm over the fixed slice and append per-question records to results/<arm>.jsonl.

The run is resumable: question ids already present in the output file are skipped.
"""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path

from eval.exec_acc import exec_match, run_gold
from t2s import linker
from t2s.agent import run_agent
from t2s.config import ARMS, RESULTS_DIR, SPIDER_DIR, db_path
from t2s.generate import OllamaChat
from t2s.schema import introspect


def _done_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines() if line}


def run_arm(arm: str, slice_path: Path, limit: int | None = None) -> Path:
    cfg = ARMS[arm]
    dev = json.loads((SPIDER_DIR / "dev.json").read_text(encoding="utf-8"))
    items = json.loads(slice_path.read_text(encoding="utf-8"))["items"][:limit]
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{arm}.jsonl"
    done = _done_ids(out)
    llm = OllamaChat(cfg.model)
    if not llm.healthy():
        raise SystemExit(f"Ollama is not reachable at {llm.url}; start it with `ollama serve`.")

    # Warm-up (not recorded): loads the LLM into VRAM and builds the embedding caches so
    # the first timed question does not pay one-off start-up costs.
    first = dev[items[0]["id"]]
    run_agent(first["question"], db_path(first["db_id"]), cfg, llm)

    meta = {"arm": arm, "model": cfg.model, "host": platform.node(), "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    (RESULTS_DIR / f"{arm}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    with out.open("a", encoding="utf-8") as fh:
        for n, it in enumerate(items, 1):
            if it["id"] in done:
                continue
            ex = dev[it["id"]]
            db = str(db_path(ex["db_id"]))
            res = run_agent(ex["question"], db, cfg, llm, db_id=ex["db_id"])
            gold_rows = run_gold(ex["query"], db)
            final = exec_match(ex["query"], res["sql"], db, gold_rows)
            first_ok = (
                final["correct"]
                if res["attempts"] == 1
                else exec_match(ex["query"], res["attempt_sqls"][0], db, gold_rows)["correct"]
            )
            all_tables = {t.name.lower() for t in introspect(db)}
            gold_t = linker.gold_tables(ex["query"], all_tables)
            rec = {
                "id": it["id"],
                "db_id": ex["db_id"],
                "hardness": it["hardness"],
                "question": ex["question"],
                "gold_sql": ex["query"],
                "pred_sql": res["sql"],
                "status": res["status"],
                "correct": final["correct"],
                "first_correct": first_ok,
                "pred_error": final["pred_error"],
                "attempts": res["attempts"],
                "attempt_sqls": res["attempt_sqls"],
                "error_trace": res["error_trace"],
                "tokens_in": res["tokens_in"],
                "tokens_out": res["tokens_out"],
                "latency_ms": res["latency_ms"],
                "n_tables": len(all_tables),
                "gold_tables": sorted(gold_t),
                "linked_tables": res["linked_tables"],
                "link_recall": (
                    linker.recall(set(res["linked_tables"]), gold_t)
                    if res["linked_tables"] is not None
                    else None
                ),
                "shots": res["shots"],
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            print(
                f"[{arm}] {n}/{len(items)} id={it['id']} {it['hardness']:<6} "
                f"{'OK ' if rec['correct'] else 'BAD'} att={rec['attempts']} {rec['latency_ms']:.0f}ms"
            )
    return out
