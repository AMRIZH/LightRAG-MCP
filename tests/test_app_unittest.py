from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_api_keys  # noqa: E402
from scripts import run_server  # noqa: E402


class TestTokenAndFallbackLogic(unittest.TestCase):
    def test_validate_llm_max_tokens_rejects_deepseek_over_limit(self) -> None:
        cfg = {
            "LLM_BINDING_HOST": "https://api.deepseek.com/v1",
            "OPENAI_LLM_MAX_TOKENS": "9000",
        }
        msg = run_server.validate_llm_max_tokens(cfg)
        self.assertIsNotNone(msg)
        self.assertIn("[1, 8192]", msg)

    def test_validate_llm_max_tokens_accepts_deepseek_upper_bound(self) -> None:
        cfg = {
            "LLM_BINDING_HOST": "https://api.deepseek.com/v1",
            "OPENAI_LLM_MAX_TOKENS": "8192",
        }
        self.assertIsNone(run_server.validate_llm_max_tokens(cfg))

    def test_collect_embedding_keys_uses_legacy_key(self) -> None:
        cfg = {
            "EMBEDDING_BINDING_API_KEY": "legacy-key",
        }
        keys = check_api_keys.collect_embedding_keys(cfg)
        self.assertEqual(keys, ["legacy-key"])

    def test_parse_embedding_proxy_wait_seconds_defaults_to_30(self) -> None:
        wait_seconds, err = run_server.parse_embedding_proxy_wait_seconds({})
        self.assertEqual(wait_seconds, 30)
        self.assertIsNone(err)

    def test_parse_embedding_proxy_max_429_retries_rejects_negative(self) -> None:
        retries, err = run_server.parse_embedding_proxy_max_429_retries(
            {"EMBEDDING_PROXY_MAX_429_RETRIES": "-1"}
        )
        self.assertEqual(retries, 0)
        self.assertIn(">= 0", err or "")

    @patch("scripts.check_api_keys.test_embedding_with_key")
    def test_embedding_uses_second_key_when_first_fails(self, mock_test_embedding_with_key) -> None:
        mock_test_embedding_with_key.side_effect = [
            (False, "401 unauthorized"),
            (True, "ok"),
        ]

        cfg = {
            "EMBEDDING_BINDING_HOST": "https://api.voyageai.com/v1",
            "EMBEDDING_MODEL": "voyage-4-large",
            "EMBEDDING_BINDING_API_KEY_1": "key-1",
            "EMBEDDING_BINDING_API_KEY_2": "key-2",
            "EMBEDDING_REQUIRED_VALID_KEYS": "1",
        }

        ok, msg = check_api_keys.test_embedding(cfg, timeout=5)
        self.assertTrue(ok)
        self.assertIn("passed preflight", msg)

    @patch("scripts.check_api_keys.test_embedding_with_key")
    def test_embedding_fails_when_required_valid_keys_not_met(self, mock_test_embedding_with_key) -> None:
        mock_test_embedding_with_key.side_effect = [
            (True, "ok"),
            (True, "ok"),
            (False, "401 unauthorized"),
        ]

        cfg = {
            "EMBEDDING_BINDING_HOST": "https://api.voyageai.com/v1",
            "EMBEDDING_MODEL": "voyage-4-large",
            "EMBEDDING_BINDING_API_KEY_1": "key-1",
            "EMBEDDING_BINDING_API_KEY_2": "key-2",
            "EMBEDDING_BINDING_API_KEY_3": "key-3",
            "EMBEDDING_REQUIRED_VALID_KEYS": "3",
        }

        ok, msg = check_api_keys.test_embedding(cfg, timeout=5)
        self.assertFalse(ok)
        self.assertIn("require at least 3", msg)

    def test_run_server_main_enables_round_robin_proxy_for_multiple_keys(self) -> None:
        cfg = {
            "LLM_BINDING_API_KEY": "llm-valid-key",
            "LLM_BINDING_HOST": "https://api.deepseek.com/v1",
            "OPENAI_LLM_MAX_TOKENS": "8192",
            "EMBEDDING_BINDING_HOST": "https://api.voyageai.com/v1",
            "EMBEDDING_MODEL": "voyage-4-large",
            "EMBEDDING_BINDING_API_KEY_1": "key-1",
            "EMBEDDING_BINDING_API_KEY_2": "key-2",
            "EMBEDDING_PROXY_PORT": "8877",
            "EMBEDDING_PROXY_429_WAIT_SECONDS": "15",
            "EMBEDDING_PROXY_MAX_429_RETRIES": "4",
        }

        proxy_mock = unittest.mock.MagicMock()

        with (
            patch("scripts.run_server.load_env_file", return_value=cfg),
            patch("scripts.run_server.test_embedding_key", side_effect=[True, True]),
            patch("scripts.run_server.start_embedding_round_robin_proxy", return_value=proxy_mock) as start_proxy,
            patch("scripts.run_server.get_server_executable", return_value=Path(sys.executable)),
            patch("scripts.run_server.is_executable_file", return_value=True),
            patch("scripts.run_server.subprocess.call", return_value=0),
            patch.object(sys, "argv", ["run_server.py"]),
            patch.dict(os.environ, {}, clear=True),
        ):
            code = run_server.main()
            self.assertEqual(code, 0)
            start_proxy.assert_called_once()
            start_proxy.assert_called_with(
                upstream_host="https://api.voyageai.com/v1",
                api_keys=["key-1", "key-2"],
                port=8877,
                retry_wait_seconds=15,
                max_retries_on_429=4,
            )
            self.assertEqual(os.environ.get("EMBEDDING_BINDING_HOST"), "http://127.0.0.1:8877/v1")
            self.assertEqual(os.environ.get("EMBEDDING_BINDING_API_KEY"), "ROUND_ROBIN_PROXY")

    def test_run_server_main_fails_when_required_keys_not_met(self) -> None:
        cfg = {
            "LLM_BINDING_API_KEY": "llm-valid-key",
            "LLM_BINDING_HOST": "https://api.deepseek.com/v1",
            "OPENAI_LLM_MAX_TOKENS": "8192",
            "EMBEDDING_BINDING_HOST": "https://api.voyageai.com/v1",
            "EMBEDDING_MODEL": "voyage-4-large",
            "EMBEDDING_BINDING_API_KEY_1": "key-1",
            "EMBEDDING_BINDING_API_KEY_2": "key-2",
            "EMBEDDING_BINDING_API_KEY_3": "key-3",
            "EMBEDDING_REQUIRED_VALID_KEYS": "3",
            "EMBEDDING_PROXY_PORT": "8877",
        }

        with (
            patch("scripts.run_server.load_env_file", return_value=cfg),
            patch("scripts.run_server.test_embedding_key", side_effect=[True, True, False]),
            patch("scripts.run_server.start_embedding_round_robin_proxy") as start_proxy,
            patch("scripts.run_server.get_server_executable", return_value=Path(sys.executable)),
            patch("scripts.run_server.is_executable_file", return_value=True),
            patch("scripts.run_server.subprocess.call", return_value=0),
            patch.object(sys, "argv", ["run_server.py"]),
            patch.dict(os.environ, {}, clear=True),
        ):
            code = run_server.main()
            self.assertEqual(code, 1)
            start_proxy.assert_not_called()


class TestApiSmoke(unittest.TestCase):
    BASE_URL = os.getenv("LIGHTRAG_BASE_URL", "http://127.0.0.1:9621").rstrip("/")
    TIMEOUT = int(os.getenv("LIGHTRAG_TEST_TIMEOUT", "20"))

    @classmethod
    def setUpClass(cls) -> None:
        if os.getenv("RUN_API_SMOKE", "1") != "1":
            raise unittest.SkipTest("RUN_API_SMOKE!=1; skipping live API smoke tests")

        try:
            resp = requests.get(f"{cls.BASE_URL}/health", timeout=cls.TIMEOUT)
        except requests.RequestException as exc:
            raise unittest.SkipTest(
                f"LightRAG server is not reachable at {cls.BASE_URL}. Start server to run API smoke tests. Error: {exc}"
            )

        if resp.status_code != 200:
            raise unittest.SkipTest(
                f"Health endpoint returned HTTP {resp.status_code}, expected 200. Response: {resp.text[:300]}"
            )

    def test_health_endpoint_reports_healthy(self) -> None:
        resp = requests.get(f"{self.BASE_URL}/health", timeout=self.TIMEOUT)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload.get("status"), "healthy")
        self.assertIn("configuration", payload)

    def test_openapi_and_docs_available(self) -> None:
        docs = requests.get(f"{self.BASE_URL}/docs", timeout=self.TIMEOUT)
        self.assertEqual(docs.status_code, 200)

        openapi = requests.get(f"{self.BASE_URL}/openapi.json", timeout=self.TIMEOUT)
        self.assertEqual(openapi.status_code, 200)
        spec = openapi.json()
        paths = spec.get("paths", {})

        expected_paths = {
            "/health",
            "/query",
            "/documents/upload",
            "/documents/status_counts",
            "/documents/pipeline_status",
            "/graphs",
        }
        missing = expected_paths.difference(paths.keys())
        self.assertFalse(missing, f"OpenAPI is missing expected paths: {sorted(missing)}")

    def test_key_read_endpoints_return_success(self) -> None:
        for path in [
            "/documents/status_counts",
            "/documents/pipeline_status",
            "/graph/label/popular?limit=10",
        ]:
            with self.subTest(path=path):
                resp = requests.get(f"{self.BASE_URL}{path}", timeout=self.TIMEOUT)
                self.assertEqual(resp.status_code, 200, f"{path} returned {resp.status_code}")
                self.assertIsInstance(resp.json(), (dict, list))

    def test_all_get_paths_no_server_error(self) -> None:
        spec = requests.get(f"{self.BASE_URL}/openapi.json", timeout=self.TIMEOUT).json()
        paths = spec.get("paths", {})

        for path, operations in paths.items():
            if "get" not in operations:
                continue

            call_path = path
            if "{track_id}" in call_path:
                call_path = call_path.replace("{track_id}", "smoke-test-track-id")

            with self.subTest(path=call_path):
                resp = requests.get(f"{self.BASE_URL}{call_path}", timeout=self.TIMEOUT)
                self.assertLess(
                    resp.status_code,
                    500,
                    f"GET {call_path} returned server error {resp.status_code}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
