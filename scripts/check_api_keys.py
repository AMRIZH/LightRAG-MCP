from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import requests

PLACEHOLDERS = {
    "",
    "REVOKE_AND_REPLACE",
    "your_api_key",
    "your_deepseek_api_key_here",
    "your_siliconflow_api_key_here",
}


def collect_embedding_keys(cfg: Dict[str, str]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()

    csv_keys = cfg.get("EMBEDDING_BINDING_API_KEYS", "").strip()
    if csv_keys:
        for item in csv_keys.split(","):
            key = item.strip()
            if key and not is_placeholder(key) and key not in seen:
                keys.append(key)
                seen.add(key)

    for env_name in (
        "EMBEDDING_BINDING_API_KEY_1",
        "EMBEDDING_BINDING_API_KEY_2",
        "EMBEDDING_BINDING_API_KEY_3",
        "EMBEDDING_BINDING_API_KEY_MAIN",
        "EMBEDDING_BINDING_API_KEY_FALLBACK",
        "EMBEDDING_BINDING_API_KEY",
    ):
        key = cfg.get(env_name, "").strip()
        if key and not is_placeholder(key) and key not in seen:
            keys.append(key)
            seen.add(key)

    return keys


def load_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def load_config(project_root: Path) -> Dict[str, str]:
    return load_env_file(project_root / ".env")


def build_url(base: str, path: str) -> str:
    return base.rstrip("/") + path


def is_placeholder(value: str) -> bool:
    return value.strip() in PLACEHOLDERS


def parse_required_embedding_keys(cfg: Dict[str, str]) -> Tuple[int, str | None]:
    raw = cfg.get("EMBEDDING_REQUIRED_VALID_KEYS", "2").strip()
    if not raw:
        return 2, None

    try:
        value = int(raw)
    except ValueError:
        return 0, "EMBEDDING_REQUIRED_VALID_KEYS must be an integer >= 1"

    if value < 1:
        return 0, "EMBEDDING_REQUIRED_VALID_KEYS must be >= 1"

    return value, None


def test_embedding_with_key(
    host: str,
    model: str,
    key: str,
    timeout: int,
) -> Tuple[bool, str]:
    if is_placeholder(key):
        return False, "placeholder"

    url = build_url(host, "/embeddings")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": ["healthcheck embedding"],
        "input_type": "document",
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        return False, f"request error: {exc}"

    if response.status_code == 200:
        return True, "ok"

    if response.status_code == 401:
        return False, "401 unauthorized"

    return False, f"HTTP {response.status_code}"


def test_embedding(cfg: Dict[str, str], timeout: int) -> Tuple[bool, str]:
    host = cfg.get("EMBEDDING_BINDING_HOST", "").strip()
    model = cfg.get("EMBEDDING_MODEL", "").strip()
    keys = collect_embedding_keys(cfg)
    required_valid_keys, required_error = parse_required_embedding_keys(cfg)

    if not host or not model:
        return False, "Missing embedding host/model"

    if required_error:
        return False, required_error

    if not keys:
        return (
            False,
            "Missing embedding key(s). Set one of: EMBEDDING_BINDING_API_KEY_1..3, "
            "EMBEDDING_BINDING_API_KEYS, EMBEDDING_BINDING_API_KEY_MAIN, "
            "EMBEDDING_BINDING_API_KEY_FALLBACK, or EMBEDDING_BINDING_API_KEY.",
        )

    valid_keys = 0
    failures: list[str] = []

    for idx, key in enumerate(keys, start=1):
        ok, msg = test_embedding_with_key(host, model, key, timeout)
        if ok:
            valid_keys += 1
        else:
            failures.append(f"key{idx}: {msg}")

    if valid_keys == 0:
        return False, "All embedding keys failed: " + "; ".join(failures)

    if valid_keys < required_valid_keys:
        detail = "; ".join(failures) if failures else "no failure details"
        return (
            False,
            f"Only {valid_keys} embedding key(s) passed preflight; require at least {required_valid_keys}. {detail}",
        )

    if valid_keys == 1:
        return True, "ok (1 embedding key passed preflight)"

    return True, f"ok ({valid_keys} embedding keys passed preflight; round-robin ready)"


def test_llm(cfg: Dict[str, str], timeout: int) -> Tuple[bool, str]:
    host = cfg.get("LLM_BINDING_HOST", "").strip()
    model = cfg.get("LLM_MODEL", "").strip()
    key = cfg.get("LLM_BINDING_API_KEY", "").strip()
    max_tokens_raw = cfg.get("OPENAI_LLM_MAX_TOKENS", "").strip()

    if not host or not model or not key:
        return False, "Missing llm host/model/api key"

    if is_placeholder(key):
        return False, "LLM key is placeholder. Replace LLM_BINDING_API_KEY in .env"

    if max_tokens_raw:
        try:
            max_tokens = int(max_tokens_raw)
        except ValueError:
            return False, "OPENAI_LLM_MAX_TOKENS must be an integer"

        # DeepSeek's OpenAI-compatible endpoint currently allows [1, 8192].
        if "deepseek.com" in host.lower() and not (1 <= max_tokens <= 8192):
            return (
                False,
                "OPENAI_LLM_MAX_TOKENS out of range for DeepSeek; use a value in [1, 8192]",
            )

    url = build_url(host, "/chat/completions")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        return False, f"Request error: {exc}"

    if response.status_code == 200:
        return True, "ok"

    if response.status_code == 401:
        return False, "401 unauthorized: llm key invalid or revoked"

    return False, f"HTTP {response.status_code}: llm endpoint rejected request"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate LightRAG upstream provider keys before ingestion/query."
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root that contains .env",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout seconds for each provider check",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM provider check",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="Skip embedding provider check",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON result",
    )

    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    cfg = load_config(root)

    results: Dict[str, Dict[str, str | bool]] = {}

    if not args.skip_llm:
        ok, msg = test_llm(cfg, timeout=args.timeout)
        results["llm"] = {"ok": ok, "message": msg}

    if not args.skip_embedding:
        ok, msg = test_embedding(cfg, timeout=args.timeout)
        results["embedding"] = {"ok": ok, "message": msg}

    all_ok = all(entry["ok"] for entry in results.values()) if results else True

    if args.json:
        print(json.dumps({"ok": all_ok, "results": results}, indent=2))
    else:
        for name, entry in results.items():
            status = "PASS" if entry["ok"] else "FAIL"
            print(f"[{status}] {name}: {entry['message']}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
