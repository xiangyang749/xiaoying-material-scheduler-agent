import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class ModelError(Exception):
    pass


class DeepSeek:
    label = "live_deepseek"

    def __init__(self, config_path=None):
        config = json.loads(Path(config_path).read_text(encoding="utf-8-sig")) if config_path else {}
        self.key = os.environ.get("DEEPSEEK_API_KEY") or config.get("api_key", "")
        self.model = os.environ.get("DEEPSEEK_MODEL") or config.get("model", "")
        if config.get("base_url", "https://api.deepseek.com").rstrip("/") != "https://api.deepseek.com":
            raise ModelError("This adapter accepts only the official DeepSeek endpoint")
        if not self.key or not self.model:
            raise ModelError("Set DEEPSEEK_API_KEY and DEEPSEEK_MODEL; no automatic mock fallback")

    def next(self, messages, tools):
        body = json.dumps({"model": self.model, "messages": messages, "tools": tools,
                           "tool_choice": "auto", "stream": False, "max_tokens": 1024}).encode()
        req = Request("https://api.deepseek.com/chat/completions", data=body,
                      headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=30) as response:
                message = json.load(response)["choices"][0]["message"]
            # Keep only public content and tool protocol, never collect private reasoning.
            if not isinstance(message, dict):
                raise ValueError("Invalid message")
            return {k: message[k] for k in ("role", "content", "tool_calls") if k in message}
        except HTTPError as exc:
            raise ModelError(f"DeepSeek HTTP {exc.code}") from None
        except (URLError, TimeoutError, KeyError, ValueError, IndexError) as exc:
            raise ModelError("DeepSeek transport or response error: " + type(exc).__name__) from None


class Mock:
    """Deterministic test double, explicitly NOT evidence of model reasoning."""
    label = "offline_mock"
    model = "deterministic-test-double"

    def next(self, messages, tools):
        observations = [json.loads(x["content"]) for x in messages if x["role"] == "tool"]
        last = observations[-1] if observations else None
        args = {}
        if last is None:
            name, reason = "read_material", "Read material metadata before review."
        elif "material" in last:
            name, reason = "check_rules", "Apply review rules to observed metadata."
        elif last.get("status") == "approved":
            name, reason = "query_slots", "Review passed; inspect actual slot availability."
        elif "available" in last and last["available"]:
            name = "save_draft"
            args["slot"] = last["available"][0]
            reason = "Requested slot is available." if last["requested_available"] else "Conflict observed; propose an alternative subject to consent."
        elif last.get("error") == "slot_conflict":
            name, reason = "query_slots", "Write-time conflict observed; refresh available slots."
        else:
            name, reason = "finish", "Stop based on the observed review, availability, or save result."
        args["reason"] = reason
        return {"role": "assistant", "content": None, "tool_calls": [{"id": f"mock_{len(observations)+1}",
                "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
