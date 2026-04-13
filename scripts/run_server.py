from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import count
from typing import Dict
from urllib.parse import urlsplit

import requests

PLACEHOLDERS = {
    "",
    "REVOKE_AND_REPLACE",
    "your_api_key",
    "your_deepseek_api_key_here",
    "your_siliconflow_api_key_here",
}

REQUIRED_KEYS = (
    "LLM_BINDING_API_KEY",
)


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


def collect_embedding_keys(cfg: Dict[str, str]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()

    csv_keys = cfg.get("EMBEDDING_BINDING_API_KEYS", "").strip()
    if csv_keys:
        for item in csv_keys.split(","):
            key = item.strip()
            if key and key not in PLACEHOLDERS and key not in seen:
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
        if key and key not in PLACEHOLDERS and key not in seen:
            keys.append(key)
            seen.add(key)

    return keys


def test_embedding_key(host: str, model: str, key: str, timeout: int = 20) -> bool:
    if key in PLACEHOLDERS:
        return False

    try:
        response = requests.post(
            host.rstrip("/") + "/embeddings",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": ["healthcheck embedding"],
                "input_type": "document",
            },
            timeout=timeout,
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


def start_embedding_round_robin_proxy(
    upstream_host: str,
    api_keys: list[str],
    port: int,
) -> ThreadingHTTPServer:
    request_counter = count(0)
    request_lock = threading.Lock()

    class EmbeddingProxyHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def do_POST(self) -> None:  # noqa: N802
            request_path = urlsplit(self.path).path.rstrip("/")
            if request_path not in ("/embeddings", "/v1/embeddings"):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error":"not_found"}')
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length > 0 else b""

            with request_lock:
                idx = next(request_counter) % len(api_keys)
                key = api_keys[idx]

            forward_path = request_path
            if forward_path.startswith("/v1/"):
                forward_path = forward_path[len("/v1") :]

            upstream_url = upstream_host.rstrip("/") + forward_path

            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": self.headers.get("Content-Type", "application/json"),
            }

            try:
                upstream_resp = requests.post(
                    upstream_url,
                    headers=headers,
                    data=body,
                    timeout=120,
                )
            except requests.RequestException as exc:
                payload = json.dumps(
                    {
                        "error": "proxy_request_failed",
                        "message": str(exc),
                    }
                ).encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            response_body = upstream_resp.content
            self.send_response(upstream_resp.status_code)
            self.send_header(
                "Content-Type",
                upstream_resp.headers.get("Content-Type", "application/json"),
            )
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

    server = ThreadingHTTPServer(("127.0.0.1", port), EmbeddingProxyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def validate_llm_max_tokens(cfg: Dict[str, str]) -> str | None:
    host = cfg.get("LLM_BINDING_HOST", "").strip().lower()
    raw = cfg.get("OPENAI_LLM_MAX_TOKENS", "").strip()

    if not raw:
        return None

    try:
        value = int(raw)
    except ValueError:
        return "OPENAI_LLM_MAX_TOKENS must be an integer"

    # DeepSeek's OpenAI-compatible endpoint currently allows [1, 8192].
    if "deepseek.com" in host and not (1 <= value <= 8192):
        return "OPENAI_LLM_MAX_TOKENS out of range for DeepSeek; use a value in [1, 8192]"

    return None


def parse_required_embedding_keys(cfg: Dict[str, str]) -> tuple[int, str | None]:
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


def parse_embedding_proxy_port(cfg: Dict[str, str]) -> tuple[int, str | None]:
    raw = cfg.get("EMBEDDING_PROXY_PORT", "8765").strip()
    try:
        port = int(raw)
    except ValueError:
        return 0, "EMBEDDING_PROXY_PORT must be an integer between 1 and 65535"

    if not (1 <= port <= 65535):
        return 0, "EMBEDDING_PROXY_PORT must be between 1 and 65535"

    return port, None


def get_server_executable(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "lightrag-server.exe"
    return root / ".venv" / "bin" / "lightrag-server"


def is_executable_file(path: Path) -> bool:
    return path.is_file() and os.access(str(path), os.X_OK)


def get_retry_start_command(root: Path) -> str:
    if os.name == "nt":
        return r"scripts\start-server.bat"

    server_exe = get_server_executable(root)
    if server_exe.exists():
        return str(server_exe)

    return "python3 scripts/run_server.py"


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    merged = load_env_file(root / ".env")

    max_tokens_error = validate_llm_max_tokens(merged)
    if max_tokens_error:
        print(max_tokens_error)
        print(f"Update .env and rerun {get_retry_start_command(root)}")
        return 1

    for key in REQUIRED_KEYS:
        value = merged.get(key, "").strip()
        if value in PLACEHOLDERS:
            print(f"{key} is missing or placeholder. Update .env first.")
            return 1
        os.environ[key] = value

    emb_host = merged.get("EMBEDDING_BINDING_HOST", "").strip()
    emb_model = merged.get("EMBEDDING_MODEL", "").strip()
    embedding_keys = collect_embedding_keys(merged)
    required_valid_keys, required_error = parse_required_embedding_keys(merged)

    if not emb_host or not emb_model:
        print("EMBEDDING_BINDING_HOST or EMBEDDING_MODEL is missing in .env.")
        return 1

    if required_error:
        print(required_error)
        return 1

    selected_embedding_key = ""
    validated_keys: list[str] = []
    proxy_server: ThreadingHTTPServer | None = None
    skip_probe = os.environ.get("LIGHTRAG_SKIP_KEYCHECK", "0") == "1"

    if not embedding_keys:
        print(
            "No valid embedding key found. Set EMBEDDING_BINDING_API_KEY_1..3 (or EMBEDDING_BINDING_API_KEYS) in .env."
        )
        return 1

    if skip_probe:
        validated_keys = embedding_keys
    else:
        for key in embedding_keys:
            if test_embedding_key(emb_host, emb_model, key):
                validated_keys.append(key)

    if not validated_keys:
        print(
            "No valid embedding key passed preflight. Check EMBEDDING_BINDING_API_KEY_1..3 (or EMBEDDING_BINDING_API_KEYS) in .env."
        )
        return 1

    if len(validated_keys) < required_valid_keys:
        print(
            f"Only {len(validated_keys)} embedding key(s) passed preflight; require at least {required_valid_keys}."
        )
        print(
            "Update EMBEDDING_BINDING_API_KEY_1..3 (or EMBEDDING_BINDING_API_KEYS) in .env."
        )
        return 1

    if len(validated_keys) >= 2:
        proxy_port, proxy_port_error = parse_embedding_proxy_port(merged)
        if proxy_port_error:
            print(proxy_port_error)
            return 1

        try:
            proxy_server = start_embedding_round_robin_proxy(
                upstream_host=emb_host,
                api_keys=validated_keys,
                port=proxy_port,
            )
        except OSError as exc:
            print(f"Failed to start embedding round-robin proxy on 127.0.0.1:{proxy_port}: {exc}")
            return 1

        os.environ["EMBEDDING_BINDING_HOST"] = f"http://127.0.0.1:{proxy_port}/v1"
        os.environ["EMBEDDING_BINDING_API_KEY"] = "ROUND_ROBIN_PROXY"
        print(f"Embedding round-robin enabled across {len(validated_keys)} keys via local proxy on 127.0.0.1:{proxy_port}")
    else:
        selected_embedding_key = validated_keys[0]
        os.environ["EMBEDDING_BINDING_API_KEY"] = selected_embedding_key

    for key_name in (
        "EMBEDDING_BINDING_API_KEY_1",
        "EMBEDDING_BINDING_API_KEY_2",
        "EMBEDDING_BINDING_API_KEY_3",
        "EMBEDDING_BINDING_API_KEY_MAIN",
        "EMBEDDING_BINDING_API_KEY_FALLBACK",
        "EMBEDDING_BINDING_API_KEYS",
    ):
        if key_name in merged:
            os.environ[key_name] = merged[key_name]

    server_exe = get_server_executable(root)
    if not server_exe.exists():
        print(f"LightRAG server binary not found at: {server_exe}")
        print("Run scripts\\setup.bat first.")
        return 1

    if not is_executable_file(server_exe):
        print(f"LightRAG server binary is not executable: {server_exe}")
        return 1

    cmd = [str(server_exe)] + sys.argv[1:]
    try:
        return subprocess.call(cmd, cwd=str(root), env=os.environ.copy())
    finally:
        if proxy_server is not None:
            proxy_server.shutdown()
            proxy_server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
