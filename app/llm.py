"""
Multi-Provider LLM Engine for KINETIC-ZERO.
Supports local Ollama models (llama3.2, qwen2.5) and cloud Gemini API,
with deterministic disk caching, offline replay, and usage telemetry.
Follows SPEC.txt Section 6.9.
"""

import os
import json
import hashlib
import time
import threading
import urllib.request
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = os.environ.get("K0_CACHE_DIR", ".cache/llm")
OFFLINE_MODE = os.environ.get("K0_OFFLINE", "0") == "1"
LLM_PROVIDER = os.environ.get("K0_LLM_PROVIDER", "ollama").lower()
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "30.0"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


class CacheMiss(Exception):
    """Raised when running in offline replay mode and a cache entry is not found."""
    pass


class UsageTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self.calls = 0
        self.tokens = 0
        self.cache_hits = 0

    def record_call(self, tokens: int = 0, hit: bool = False):
        with self._lock:
            self.calls += 1
            self.tokens += tokens
            if hit:
                self.cache_hits += 1

    def reset(self):
        with self._lock:
            self.calls = 0
            self.tokens = 0
            self.cache_hits = 0

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "calls": self.calls,
                "tokens": self.tokens,
                "cache_hits": self.cache_hits,
            }


usage_tracker = UsageTracker()


def get_llm_status() -> Dict[str, Any]:
    """Inspects active LLM configuration and tests connectivity."""
    provider = os.environ.get("K0_LLM_PROVIDER", LLM_PROVIDER).lower()
    host = os.environ.get("OLLAMA_HOST", OLLAMA_HOST)
    model = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL)

    if provider == "ollama":
        try:
            req = urllib.request.Request(f"{host}/api/tags", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "provider": "ollama",
                    "status": "connected",
                    "active_model": model,
                    "host": host,
                    "available_models": models,
                }
        except Exception as e:
            return {
                "provider": "ollama",
                "status": "offline_fallback",
                "active_model": model,
                "host": host,
                "error": str(e),
            }
    else:
        api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
        return {
            "provider": "gemini",
            "status": "connected" if api_key else "missing_api_key",
            "active_model": os.environ.get("GEMINI_MODEL", GEMINI_MODEL),
        }


def _compute_cache_key(model: str, prompt: str, schema: dict, images: Optional[List[bytes]] = None) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(prompt.encode("utf-8"))
    h.update(json.dumps(schema, sort_keys=True).encode("utf-8"))
    if images:
        for img in images:
            h.update(hashlib.sha256(img).digest())
    return h.hexdigest()


def call_json(
    name: str,
    prompt: str,
    schema: dict,
    images: Optional[List[bytes]] = None,
    temperature: float = 0.0,
    force_refresh: bool = False,
) -> dict:
    """
    Executes structured JSON inference across local Ollama or cloud Gemini,
    with SHA-256 disk caching in .cache/llm.
    """
    cache_dir = os.environ.get("K0_CACHE_DIR", CACHE_DIR)
    offline_mode = os.environ.get("K0_OFFLINE", "0") == "1"
    provider = os.environ.get("K0_LLM_PROVIDER", LLM_PROVIDER).lower()
    
    active_model = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL) if provider == "ollama" else os.environ.get("GEMINI_MODEL", GEMINI_MODEL)

    os.makedirs(cache_dir, exist_ok=True)
    cache_key = _compute_cache_key(active_model, prompt, schema, images)
    cache_file = os.path.join(cache_dir, f"{name}_{cache_key}.json")

    # If active model cache miss, check fallback model key (e.g. gemini-2.5-flash)
    if not os.path.exists(cache_file):
        fallback_key = _compute_cache_key("gemini-2.5-flash", prompt, schema, images)
        fallback_file = os.path.join(cache_dir, f"{name}_{fallback_key}.json")
        if os.path.exists(fallback_file):
            cache_file = fallback_file
            cache_key = fallback_key

    # 1. Check disk cache
    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            usage_tracker.record_call(tokens=data.get("_tokens", 0), hit=True)
            return data.get("result", data)
        except Exception:
            pass

    # 2. Check offline mode
    if offline_mode:
        raise CacheMiss(f"Offline mode active and no cache entry for '{name}' (key: {cache_key})")

    result = None
    tokens_used = 0

    # 3. Provider A: Local Ollama Model
    if provider == "ollama":
        try:
            host = os.environ.get("OLLAMA_HOST", OLLAMA_HOST)
            system_instruction = (
                f"You are a strict data extraction and reasoning system. "
                f"You must output ONLY a valid JSON object matching this schema:\n"
                f"{json.dumps(schema, indent=2)}\n\n"
                f"Rules:\n"
                f"- Return raw JSON only with no markdown formatting (no ```json code blocks).\n"
                f"- Every key in the schema must be populated.\n\n"
                f"Task:\n{prompt}"
            )

            payload = {
                "model": active_model,
                "prompt": system_instruction,
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": temperature,
                },
            }

            req = urllib.request.Request(
                f"{host}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                raw_response = resp_data.get("response", "{}")
                result = json.loads(raw_response)
                tokens_used = resp_data.get("eval_count", 0) + resp_data.get("prompt_eval_count", 0)

        except Exception as e:
            # If live Ollama times out or is unreachable, raise CacheMiss to allow fallback
            raise CacheMiss(f"Ollama call failed for '{name}' ({active_model}): {e}") from e

    # 4. Provider B: Cloud Gemini API
    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
        if api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                contents = [prompt]
                if images:
                    for img in images:
                        contents.append(types.Part.from_bytes(data=img, mime_type="image/png"))

                config = types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                )

                response = client.models.generate_content(
                    model=active_model,
                    contents=contents,
                    config=config,
                )
                result = json.loads(response.text)
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    tokens_used = getattr(response.usage_metadata, "total_token_count", 0)
            except Exception as e:
                raise CacheMiss(f"Gemini API call failed for '{name}': {e}") from e
        else:
            raise CacheMiss(f"No GEMINI_API_KEY set and no cache entry for '{name}'")

    else:
        raise CacheMiss(f"Unknown LLM provider '{provider}'")

    # 5. Persist to disk cache
    payload = {
        "_name": name,
        "_key": cache_key,
        "_provider": provider,
        "_model": active_model,
        "_tokens": tokens_used,
        "_ts": time.time(),
        "result": result,
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    usage_tracker.record_call(tokens=tokens_used, hit=False)
    return result
