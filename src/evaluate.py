"""Execute scenarios and verify actual outcomes; never synthesize model traces."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from time import perf_counter
import unittest

from .agent import run
from .domain import validate_request
from .models import DeepSeek, Mock
from .store import DraftStore
from .tools import Tools

CASES = [
    ("normal", "normal", "ready", 1),
    ("missing", "missing", "needs_information", 0),
    ("risk", "risk", "blocked", 0),
    ("conflict", "conflict", "pending_confirmation", 1),
    ("save-failure", "normal", "save_failed", 0),
    ("duplicate", "normal", "ready", 1),
    ("changed-conflict", "conflict", "pending_confirmation", 1),
    ("confirmed", "confirmed", "ready", 1),
    ("no-slots", "conflict", "no_available_slots", 0),
    ("step-limit", "normal", "incomplete", 0),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--config")
    args = parser.parse_args()
    model = DeepSeek(args.config) if args.mode == "live" else Mock()
    fixture = json.loads(Path("data/catalog.json").read_text(encoding="utf-8"))
    summary = []
    for label, input_name, expected, expected_count in CASES:
        start = perf_counter()
        raw = json.loads(Path(f"examples/{input_name}.input.json").read_text(encoding="utf-8"))
        request = validate_request(raw)
        catalog = json.loads(json.dumps(fixture))
        if label == "changed-conflict":
            catalog["occupied"].append({"channel": "xiaoying", "at": "2026-11-01T19:00:00+08:00"})
        elif label == "no-slots":
            catalog["slots"] = []
        fail = label == "save-failure"
        limit = 2 if label == "step-limit" else 10
        with tempfile.TemporaryDirectory() as temp:
            store = DraftStore(Path(temp) / "drafts.sqlite")
            runs = [run(model, Tools(request, request["material_ids"][0], catalog, store, fail), limit)]
            if label == "duplicate":
                runs.append(run(model, Tools(request, "M01", catalog, store)))
            with closing(sqlite3.connect(store.path)) as db:
                row_count = db.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
        result = runs[-1]["result"]
        expected_end = "step_limit" if label == "step-limit" else "finished"
        checks = {"expected_status": result["status"] == expected,
                  "execution_status": result["execution_status"] == expected_end,
                  "draft_count": row_count == expected_count,
                  "never_published": all(not x["result"]["published"] for x in runs),
                  "hard_requirement_preserved": result["requested_at"] == request["requested_at"]}
        if label == "duplicate":
            checks["same_id"] = bool(runs[0]["result"]["receipt"] and result["receipt"] and
                                     runs[0]["result"]["receipt"].get("draft_id") == result["receipt"].get("draft_id"))
            checks["duplicate_receipt"] = bool(result["receipt"] and result["receipt"].get("duplicate"))
        if label in ("normal", "conflict", "changed-conflict", "confirmed"):
            expected_slot = "2026-11-01T20:00:00+08:00" if label in ("normal", "changed-conflict") else "2026-11-01T19:00:00+08:00"
            checks["expected_slot"] = result["suggested_at"] == expected_slot
        artifact = {"input": raw, "fixture": catalog, "fail_save": fail, "max_steps": limit,
                    "database_row_count": row_count, "checks": checks, "runs": runs,
                    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "elapsed_seconds": round(perf_counter() - start, 3)}
        path = Path(f"examples/{args.mode}-{label}.output.json")
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary.append({"case": label, "artifact": path.as_posix(), "status": result["status"],
                        "execution_status": result["execution_status"], "passed": all(checks.values()),
                        "elapsed_seconds": artifact["elapsed_seconds"]})
        print(json.dumps(summary[-1], ensure_ascii=False), flush=True)
    Path(f"examples/{args.mode}-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover("tests")
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    Path("examples/test-results.txt").write_text(stream.getvalue(), encoding="utf-8")
    print(stream.getvalue())
    return 0 if result.wasSuccessful() and all(x["passed"] for x in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
