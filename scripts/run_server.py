from __future__ import annotations

import os
import subprocess
import sys
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


def resolve_embedding_keys(cfg: Dict[str, str]) -> Tuple[str, str]:
    main = cfg.get("EMBEDDING_BINDING_API_KEY_MAIN", "").strip()
    fallback = cfg.get("EMBEDDING_BINDING_API_KEY_FALLBACK", "").strip()
    legacy = cfg.get("EMBEDDING_BINDING_API_KEY", "").strip()

    if not main and legacy:
        main = legacy

    return main, fallback


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


def get_server_executable(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "lightrag-server.exe"
    return root / ".venv" / "bin" / "lightrag-server"


def is_executable_file(path: Path) -> bool:
    return path.is_file() and os.access(str(path), os.X_OK)


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    merged = load_env_file(root / ".env")

    for key in REQUIRED_KEYS:
        value = merged.get(key, "").strip()
        if value in PLACEHOLDERS:
            print(f"{key} is missing or placeholder. Update .env first.")
            return 1
        os.environ[key] = value

    emb_host = merged.get("EMBEDDING_BINDING_HOST", "").strip()
    emb_model = merged.get("EMBEDDING_MODEL", "").strip()
    emb_main, emb_fallback = resolve_embedding_keys(merged)

    if not emb_host or not emb_model:
        print("EMBEDDING_BINDING_HOST or EMBEDDING_MODEL is missing in .env.")
        return 1

    selected_embedding_key = ""
    skip_probe = os.environ.get("LIGHTRAG_SKIP_KEYCHECK", "0") == "1"

    if skip_probe:
        if emb_main not in PLACEHOLDERS:
            selected_embedding_key = emb_main
        elif emb_fallback not in PLACEHOLDERS:
            selected_embedding_key = emb_fallback
    else:
        if test_embedding_key(emb_host, emb_model, emb_main):
            selected_embedding_key = emb_main
        elif emb_fallback not in PLACEHOLDERS and test_embedding_key(emb_host, emb_model, emb_fallback):
            selected_embedding_key = emb_fallback

    if not selected_embedding_key:
        print(
            "No valid embedding key found. Set EMBEDDING_BINDING_API_KEY_MAIN and optionally EMBEDDING_BINDING_API_KEY_FALLBACK in .env."
        )
        return 1

    os.environ["EMBEDDING_BINDING_API_KEY"] = selected_embedding_key

    server_exe = get_server_executable(root)
    if not server_exe.exists():
        print(f"LightRAG server binary not found at: {server_exe}")
        print("Run scripts\\setup.bat first.")
        return 1

    if not is_executable_file(server_exe):
        print(f"LightRAG server binary is not executable: {server_exe}")
        return 1

    cmd = [str(server_exe)] + sys.argv[1:]
    return subprocess.call(cmd, cwd=str(root), env=os.environ.copy())


if __name__ == "__main__":
    raise SystemExit(main())
