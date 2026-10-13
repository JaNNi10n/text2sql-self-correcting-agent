"""CLI: `python -m t2s ask|eval|serve`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from t2s.config import ARMS


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="t2s", description="Self-correcting text-to-SQL agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ask", help="answer one question against a SQLite file")
    a.add_argument("question")
    a.add_argument("--db", required=True, help="path to a .sqlite file")
    a.add_argument("--config", default="A3", choices=sorted(ARMS))

    e = sub.add_parser("eval", help="run an ablation arm over the fixed Spider slice")
    e.add_argument("--config", default="A3", choices=sorted(ARMS))
    e.add_argument("--slice", default="eval/slice_ids.json")
    e.add_argument("--limit", type=int, default=None, help="only the first N slice items")

    s = sub.add_parser("serve", help="start the FastAPI server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    args = p.parse_args(argv)
    if args.cmd == "ask":
        from t2s.agent import run_agent
        from t2s.generate import LLMUnavailable

        if not Path(args.db).is_file():
            print(f"database not found: {args.db}", file=sys.stderr)
            return 2
        try:
            res = run_agent(args.question, args.db, ARMS[args.config])
        except LLMUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 3
        print(json.dumps(res, indent=2, default=str))
        return 0 if res["status"] in ("ok", "empty") else 1
    if args.cmd == "eval":
        from eval import summarize
        from eval.run import run_arm

        out = run_arm(args.config, Path(args.slice), args.limit)
        print(f"wrote {out}")
        summarize.main()
        return 0
    import uvicorn

    uvicorn.run("t2s.api:app", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
