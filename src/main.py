import argparse
import json
from pathlib import Path
import sys
import sqlite3

from .agent import run
from .domain import validate_request
from .models import DeepSeek, Mock, ModelError
from .store import DraftStore
from .tools import Tools


def main():
    parser = argparse.ArgumentParser(description="Review materials and save scheduling drafts only")
    parser.add_argument("--input", required=True)
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--fixture", default="data/catalog.json")
    parser.add_argument("--db", default="drafts.sqlite")
    parser.add_argument("--output")
    parser.add_argument("--config", help="Path to private DeepSeek JSON configuration; never commit it")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--fail-save", action="store_true", help="Explicit synthetic save failure")
    args = parser.parse_args()
    try:
        request = validate_request(json.loads(Path(args.input).read_text(encoding="utf-8")))
        fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        model = DeepSeek(args.config) if args.mode == "live" else Mock()
        store = DraftStore(args.db)
        outputs = [run(model, Tools(request, mid, fixture, store, args.fail_save), args.max_steps)
                   for mid in request["material_ids"]]
        text = json.dumps({"runs": outputs}, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(text)
        return 2 if any(x["result"]["execution_status"] != "finished" for x in outputs) else 0
    except sqlite3.Error:
        print(json.dumps({"error": "storage_error"}), file=sys.stderr)
        return 2
    except (OSError, ValueError, ModelError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
