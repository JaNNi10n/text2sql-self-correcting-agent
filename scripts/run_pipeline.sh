#!/usr/bin/env bash
# Full evaluation pipeline: the four ablation arms, red-team run, official cross-check and
# failure categorisation. Every step writes into results/. Needs Ollama with qwen2.5-coder:1.5b.
#   bash scripts/run_pipeline.sh            # 1.5B arms only
#   WITH_3B=1 bash scripts/run_pipeline.sh  # also the optional qwen2.5-coder:3b arms
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/Scripts/python}"
[ -x "$PY" ] || PY=.venv/bin/python
export PYTHONIOENCODING=utf-8
mkdir -p results
ARMS="${ARMS:-A0 A1 A2 A3 A1R}"
[ "${WITH_3B:-0}" = "1" ] && ARMS="$ARMS A0-3b A3-3b"
for arm in $ARMS; do
  "$PY" -u -m t2s eval --config "$arm" --slice eval/slice_ids.json 2>&1 | tee "results/run_${arm}.log"
done
"$PY" -u -m eval.redteam 2>&1 | tee results/run_redteam.log
"$PY" -u -m eval.crosscheck --arm A3 2>&1 | tee results/run_crosscheck.log
"$PY" -u -m eval.failures --arm A3 2>&1 | tee results/run_failures.log
"$PY" -u -m eval.summarize > /dev/null
