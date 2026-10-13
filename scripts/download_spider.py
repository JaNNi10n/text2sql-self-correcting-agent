"""Download Spider 1.0 (Yu et al., 2018) and the official test-suite evaluation scripts.

* Spider (dev/train JSON + 166 SQLite DBs) -> ./spider   (gitignored; CC BY-SA 4.0)
  1st try: official Google Drive release linked from https://yale-lily.github.io/spider
  fallback: a Hugging Face mirror of the original spider.zip (Drive often hits its
  "too many downloads" quota). Either way, dev.json is verified question-by-question
  against the official `xlangai/spider` validation split before it is accepted.
* taoyds/test-suite-sql-eval (Apache-2.0) evaluation.py + process_sql.py
  -> ./third_party/test_suite (gitignored). Used for Spider hardness labels and the
  optional official cross-check.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GDRIVE_ID = "1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J"
HF_MIRROR = "https://huggingface.co/datasets/Sreenath/spider/resolve/main/spider_v1.zip"
OFFICIAL_DEV = (
    "https://huggingface.co/datasets/xlangai/spider/resolve/main/spider/"
    "validation-00000-of-00001.parquet"
)
TS_COMMIT = "e97acc546ecbee8fa27fa8dbf025ef61493a876c"
TS_BASE = f"https://raw.githubusercontent.com/taoyds/test-suite-sql-eval/{TS_COMMIT}/"


def _fetch(url: str, dest: Path) -> None:
    print(f"GET {url}")
    with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _download_zip(zpath: Path) -> None:
    try:
        import gdown

        gdown.download(id=GDRIVE_ID, output=str(zpath), quiet=False)
        if zpath.exists() and zipfile.is_zipfile(zpath):
            return
    except Exception as exc:  # Drive quota errors are common
        print(f"Google Drive download failed ({type(exc).__name__}); using HF mirror")
    _fetch(HF_MIRROR, zpath)


def _verify_dev(target: Path) -> None:
    import pandas as pd

    dev = json.loads((target / "dev.json").read_text(encoding="utf-8"))
    buf = io.BytesIO(urllib.request.urlopen(OFFICIAL_DEV, timeout=120).read())
    ref = pd.read_parquet(buf)
    assert len(dev) == len(ref) == 1034, (len(dev), len(ref))
    for d, (_, r) in zip(dev, ref.iterrows()):
        assert d["question"] == r["question"] and d["query"] == r["query"], d["question"]
        assert d["db_id"] == r["db_id"]
    print("dev.json verified against official xlangai/spider validation split (1034/1034)")


def _get_test_suite() -> None:
    out = ROOT / "third_party" / "test_suite"
    out.mkdir(parents=True, exist_ok=True)
    for name in ("evaluation.py", "process_sql.py", "exec_eval.py", "parse.py", "LICENSE"):
        if not (out / name).exists():
            _fetch(TS_BASE + name, out / name)


def main() -> int:
    target = ROOT / "spider"
    if not ((target / "dev.json").exists() and (target / "database").is_dir()):
        zpath = ROOT / "spider_data.zip"
        if not zpath.exists():
            _download_zip(zpath)
        tmp = ROOT / "_spider_extract"
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(zpath) as zf:
            for name in zf.namelist():  # refuse path traversal
                if name.startswith("/") or ".." in Path(name).parts:
                    raise RuntimeError(f"unsafe path in archive: {name}")
            zf.extractall(tmp)
        inner = next(p.parent for p in tmp.rglob("dev.json") if "__MACOSX" not in p.parts)
        shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(inner), str(target))
        shutil.rmtree(tmp, ignore_errors=True)
        zpath.unlink()
    _verify_dev(target)
    _get_test_suite()
    n_db = sum(1 for p in (target / "database").iterdir() if p.is_dir())
    print(f"Spider ready at {target} ({n_db} databases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
