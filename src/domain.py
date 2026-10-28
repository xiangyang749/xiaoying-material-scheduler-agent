import hashlib
import json
from datetime import datetime


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def timestamp(value):
    dt = datetime.fromisoformat(value)
    if dt.utcoffset() is None:
        raise ValueError("Time must include timezone offset")
    return dt.isoformat()


def validate_request(raw):
    if not isinstance(raw, dict):
        raise ValueError("Request must be an object")
    for key in ("request_id", "channel", "requested_at"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError(f"Missing or invalid {key}")
    ids = raw.get("material_ids")
    if not isinstance(ids, list) or not ids or len(ids) > 20:
        raise ValueError("material_ids must contain 1-20 IDs")
    if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("material_ids must be unique nonempty strings")
    hard = raw.get("hard_time", True)
    if not isinstance(hard, bool):
        raise ValueError("hard_time must be boolean")
    approved = raw.get("approved_slots", [])
    if not isinstance(approved, list) or any(not isinstance(x, str) for x in approved):
        raise ValueError("approved_slots must be a list of timezone-aware timestamps")
    return {"request_id": raw["request_id"], "channel": raw["channel"],
            "material_ids": ids, "requested_at": timestamp(raw["requested_at"]),
            "hard_time": hard, "approved_slots": [timestamp(x) for x in approved]}


def fingerprint(request, material_id):
    item = {**request, "material_ids": [material_id]}
    return hashlib.sha256(canonical(item).encode()).hexdigest()


def review(material, rules):
    if material is None:
        return {"status": "needs_information", "reasons": ["material_not_found"]}
    missing = [key for key in rules["required_fields"] if material.get(key) in (None, "", [])]
    if missing:
        return {"status": "needs_information", "reasons": ["missing:" + k for k in missing]}
    risks = []
    if not isinstance(material["title"], str):
        risks.append("invalid_title")
    if material.get("rights") != "cleared":
        risks.append("rights_not_cleared")
    title = str(material["title"]).casefold()
    risks.extend("blocked_term:" + term for term in rules["blocked_terms"] if term.casefold() in title)
    duration = material.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
        risks.append("invalid_duration")
    return {"status": "blocked" if risks else "approved", "reasons": risks}
