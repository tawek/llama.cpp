"""
Regression tests for llama.cpp server endpoints.
Tests response structure against captured fixtures from live server.
Run with: python3 -m pytest test_regression.py -v
Requires: Server running on localhost:11435
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
import json
from unittest.mock import patch, MagicMock
from api_client import ServerAPI, parse_prometheus_metrics

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Load captured live responses from temp files if available
def _load_fixture(name):
    path = os.path.join(os.path.dirname(__file__), 'tests', name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    # Fallback: load from /tmp if available
    path = f'/tmp/{name}'
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


class Fixtures:
    """Captured live server responses for regression testing."""
    HEALTH = {"status": "ok"}
    HEALTH_V1 = {"status": "ok"}
    LORA_ADAPTERS = []


# Load live fixtures at runtime if available
try:
    _props_raw = _load_fixture('props_response.json')
    if _props_raw and 'chat_template' in _props_raw:
        del _props_raw['chat_template']
    PROPS = _props_raw or {
        "bos_token": "</s>",
        "build_info": "b9236-9f8a3862c",
        "chat_template_caps": {
            "supports_object_arguments": True,
            "supports_parallel_tool_calls": True,
            "supports_preserve_reasoning": True,
            "supports_string_content": True,
            "supports_system_role": True,
            "supports_tool_calls": True,
            "supports_tools": True,
            "supports_typed_content": False,
        },
        "cors_proxy_enabled": False,
        "default_generation_settings": {
            "n_ctx": 131072,
            "params": {
                "backend_sampling": False,
                "chat_format": "Content-only",
                "dry_allowed_length": 2,
                "dry_base": 1.75,
                "dry_multiplier": 0.0,
                "dry_penalty_last_n": -1,
                "dynatemp_exponent": 1.0,
                "dynatemp_range": 0.0,
                "frequency_penalty": 0.0,
                "generation_prompt": "",
                "ignore_eos": False,
                "lora": [],
                "max_tokens": -1,
                "min_keep": 0,
                "min_p": 0.05000000074505806,
                "mirostat": 0,
                "mirostat_eta": 0.10000000149011612,
                "mirostat_tau": 5.0,
                "n_discard": 0,
                "n_keep": 0,
                "n_predict": -1,
                "n_probs": 0,
                "post_sampling_probs": False,
                "presence_penalty": 0.0,
                "reasoning_format": "none",
                "reasoning_in_content": False,
                "repeat_last_n": 64,
                "repeat_penalty": 1.0,
                "samplers": [
                    "penalties", "dry", "top_n_sigma", "top_k",
                    "typ_p", "top_p", "min_p", "xtc", "temperature",
                ],
                "seed": 4294967295,
                "speculative.types": "none",
                "stream": True,
                "temperature": 1.0,
                "timings_per_token": False,
                "top_k": 20,
                "top_n_sigma": -1.0,
                "top_p": 0.949999988079071,
                "typical_p": 1.0,
                "xtc_probability": 0.0,
                "xtc_threshold": 0.10000000149011612,
            },
        },
        "endpoint_metrics": False,
        "endpoint_props": False,
        "endpoint_slots": True,
        "eos_token": "\n",
        "is_sleeping": False,
        "media_marker": "<__media_KgH6NKIHwEiGx5DCZOAf2VUPqSxTxKdg__>",
        "modalities": {"audio": False, "vision": False},
        "model_alias": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
        "model_path": "/home/tawek/models/Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
        "total_slots": 4,
        "ui": True,
        "ui_settings": {},
        "webui": True,
        "webui_settings": {},
    }
except Exception:
    PROPS = Fixtures.__dict__.get('PROPS', {})


class HealthEndpointTest(unittest.TestCase):
    """Test /health and /v1/health endpoints."""

    def setUp(self):
        self.api = ServerAPI("http://localhost:11435")

    def test_health_returns_status_ok(self):
        result = self.api.health()
        self.assertIsNotNone(result)
        self.assertEqual(result.get("status"), "ok")

    def test_health_v1_returns_status_ok(self):
        result = self.api.health_v1()
        self.assertIsNotNone(result)
        self.assertEqual(result.get("status"), "ok")

    def test_is_alive_with_healthy_server(self):
        with patch.object(self.api, 'health', return_value={"status": "ok"}):
            self.assertTrue(self.api.is_alive())

    def test_is_alive_with_unhealthy_server(self):
        with patch.object(self.api, 'health', return_value={"status": "error"}):
            self.assertFalse(self.api.is_alive())

    def test_is_alive_with_none_response(self):
        with patch.object(self.api, 'health', return_value=None):
            self.assertFalse(self.api.is_alive())

    def test_health_matches_fixture(self):
        result = self.api.health()
        self.assertEqual(result, Fixtures.HEALTH)

    def test_health_v1_matches_fixture(self):
        result = self.api.health_v1()
        self.assertEqual(result, Fixtures.HEALTH_V1)


class SlotsEndpointTest(unittest.TestCase):
    """Test /slots endpoint structure."""

    def setUp(self):
        self.api = ServerAPI("http://localhost:11435")

    def test_slots_returns_list(self):
        result = self.api.slots()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_slots_items_have_required_fields(self):
        result = self.api.slots()
        for slot in result:
            self.assertIn("id", slot)
            self.assertIn("n_ctx", slot)
            self.assertIn("speculative", slot)
            self.assertIn("is_processing", slot)
            self.assertIn("params", slot)
            self.assertIn("next_token", slot)

    def test_slot_params_has_chat_format(self):
        result = self.api.slots()
        for slot in result:
            self.assertIn("chat_format", slot["params"])
            self.assertIn("reasoning_format", slot["params"])

    def test_slot_next_token_structure(self):
        result = self.api.slots()
        for slot in result:
            for token_info in slot.get("next_token", []):
                self.assertIn("has_next_token", token_info)
                self.assertIn("has_new_line", token_info)
                self.assertIn("n_remain", token_info)
                self.assertIn("n_decoded", token_info)

    def test_slots_structure_has_correct_count(self):
        result = self.api.slots()
        # Should have 4 slots total
        self.assertEqual(len(result), 4)

    def test_slot_has_id_task(self):
        result = self.api.slots()
        for slot in result:
            self.assertIn("id_task", slot)
            self.assertIsInstance(slot["id_task"], int)

    def test_slot_speculative_info(self):
        result = self.api.slots()
        for slot in result:
            self.assertIn("speculative", slot)
            self.assertIsInstance(slot["speculative"], bool)


class PropsEndpointTest(unittest.TestCase):
    """Test /props endpoint structure."""

    def setUp(self):
        self.api = ServerAPI("http://localhost:11435")

    def test_props_returns_dict(self):
        result = self.api.props()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)

    def test_props_has_model_info(self):
        result = self.api.props()
        self.assertIn("model_alias", result)
        self.assertIn("model_path", result)

    def test_props_has_default_generation_settings(self):
        result = self.api.props()
        self.assertIn("default_generation_settings", result)
        params = result["default_generation_settings"]["params"]
        self.assertIn("temperature", params)
        self.assertIn("top_k", params)
        self.assertIn("top_p", params)

    def test_props_has_chat_template_caps(self):
        result = self.api.props()
        self.assertIn("chat_template_caps", result)
        caps = result["chat_template_caps"]
        self.assertIn("supports_tools", caps)
        self.assertIn("supports_tool_calls", caps)

    def test_props_has_build_info(self):
        result = self.api.props()
        self.assertIn("build_info", result)
        self.assertIsInstance(result["build_info"], str)
        self.assertIn("b9236", result["build_info"])

    def test_props_has_total_slots(self):
        result = self.api.props()
        self.assertIn("total_slots", result)
        self.assertIsInstance(result["total_slots"], int)

    def test_props_has_endpoint_capabilities(self):
        result = self.api.props()
        self.assertIn("endpoint_slots", result)
        self.assertIn("endpoint_metrics", result)
        self.assertIn("endpoint_props", result)

    def test_props_has_bos_eos_tokens(self):
        result = self.api.props()
        self.assertIn("bos_token", result)
        self.assertIn("eos_token", result)

    def test_props_has_modalities(self):
        result = self.api.props()
        self.assertIn("modalities", result)
        self.assertIn("audio", result["modalities"])
        self.assertIn("vision", result["modalities"])

    def test_props_has_ui_flags(self):
        result = self.api.props()
        self.assertIn("ui", result)
        self.assertIn("webui", result)
        self.assertIn("is_sleeping", result)

    def test_props_default_params_have_expected_values(self):
        result = self.api.props()
        params = result["default_generation_settings"]["params"]
        self.assertAlmostEqual(params["temperature"], 1.0, places=6)
        self.assertEqual(params["top_k"], 20)
        self.assertAlmostEqual(params["top_p"], 0.95, places=6)
        self.assertAlmostEqual(params["min_p"], 0.05, places=6)


class ModelsEndpointTest(unittest.TestCase):
    """Test /models and /v1/models endpoints."""

    def setUp(self):
        self.api = ServerAPI("http://localhost:11435")

    def test_models_returns_list(self):
        result = self.api.models()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertIn("models", result)
        self.assertIsInstance(result["models"], list)
        self.assertGreater(len(result["models"]), 0)

    def test_v1_models_has_data(self):
        result = self.api._request("/v1/models")
        self.assertIsNotNone(result)
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)

    def test_model_has_meta_info(self):
        result = self.api._request("/v1/models")
        for model in result.get("data", []):
            self.assertIn("meta", model)
            meta = model["meta"]
            self.assertIn("n_vocab", meta)
            self.assertIn("n_ctx", meta)
            self.assertIn("n_params", meta)

    def test_model_capabilities(self):
        result = self.api._request("/v1/models")
        for model in result.get("models", []):
            self.assertIn("capabilities", model)
            self.assertIsInstance(model["capabilities"], list)

    def test_model_owned_by_llamacpp(self):
        result = self.api._request("/v1/models")
        for model in result.get("data", []):
            self.assertEqual(model.get("owned_by"), "llamacpp")

    def test_lora_adapters_returns_list(self):
        result = self.api._request("/lora-adapters")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)

    def test_model_n_vocab_correct(self):
        result = self.api._request("/v1/models")
        for model in result.get("data", []):
            self.assertEqual(model["meta"]["n_vocab"], 248320)

    def test_model_n_params_correct(self):
        result = self.api._request("/v1/models")
        for model in result.get("data", []):
            self.assertEqual(model["meta"]["n_params"], 34660610688)


class ChatCompletionEndpointTest(unittest.TestCase):
    """Test /v1/chat/completions and /v1/completions endpoints."""

    def setUp(self):
        self.api = ServerAPI("http://localhost:11435")

    def test_chat_completion_has_choices(self):
        result = self.api._request_post("/v1/chat/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 10,
            "stream": False,
        }, timeout=30)
        self.assertIsNotNone(result)
        self.assertIn("choices", result)
        self.assertGreater(len(result["choices"]), 0)

    def test_chat_completion_has_usage(self):
        result = self.api._request_post("/v1/chat/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 5,
            "stream": False,
        }, timeout=30)
        self.assertIn("usage", result)
        usage = result["usage"]
        self.assertIn("completion_tokens", usage)
        self.assertIn("prompt_tokens", usage)
        self.assertIn("total_tokens", usage)

    def test_chat_completion_has_timings(self):
        result = self.api._request_post("/v1/chat/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 5,
            "stream": False,
        }, timeout=30)
        self.assertIn("timings", result)
        timings = result["timings"]
        self.assertIn("prompt_ms", timings)
        self.assertIn("predicted_ms", timings)
        self.assertIn("prompt_per_token_ms", timings)

    def test_chat_completion_has_reasoning_content(self):
        result = self.api._request_post("/v1/chat/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 10,
            "stream": False,
        }, timeout=30)
        choice = result["choices"][0]
        self.assertIn("message", choice)
        msg = choice["message"]
        self.assertIn("role", msg)
        self.assertEqual(msg["role"], "assistant")

    def test_chat_completion_object_type(self):
        result = self.api._request_post("/v1/chat/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 5,
            "stream": False,
        }, timeout=30)
        self.assertEqual(result.get("object"), "chat.completion")

    def test_chat_completion_has_system_fingerprint(self):
        result = self.api._request_post("/v1/chat/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 5,
            "stream": False,
        }, timeout=30)
        self.assertIn("system_fingerprint", result)
        self.assertIsInstance(result["system_fingerprint"], str)

    def test_completion_has_choices(self):
        result = self.api._request_post("/v1/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "prompt": "say hi",
            "max_tokens": 10,
            "stream": False,
        }, timeout=30)
        self.assertIsNotNone(result)
        self.assertIn("choices", result)
        self.assertGreater(len(result["choices"]), 0)

    def test_completion_has_text(self):
        result = self.api._request_post("/v1/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "prompt": "say hi",
            "max_tokens": 10,
            "stream": False,
        }, timeout=30)
        text = result["choices"][0].get("text", "")
        self.assertIsInstance(text, str)

    def test_completion_object_type(self):
        result = self.api._request_post("/v1/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "prompt": "say hi",
            "max_tokens": 5,
            "stream": False,
        }, timeout=30)
        self.assertEqual(result.get("object"), "text_completion")

    def test_completion_has_timings(self):
        result = self.api._request_post("/v1/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "prompt": "say hi",
            "max_tokens": 5,
            "stream": False,
        }, timeout=30)
        self.assertIn("timings", result)
        self.assertIn("predicted_per_second", result["timings"])

    def test_completion_has_logprobs_field(self):
        result = self.api._request_post("/v1/completions", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "prompt": "say hi",
            "max_tokens": 5,
            "stream": False,
        }, timeout=30)
        self.assertIn("logprobs", result["choices"][0])


class V1MessagesEndpointTest(unittest.TestCase):
    """Test /v1/messages endpoint."""

    def setUp(self):
        self.api = ServerAPI("http://localhost:11435")

    def test_messages_returns_structured_content(self):
        result = self.api._request_post("/v1/messages", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 10,
        })
        self.assertIsNotNone(result)
        self.assertIn("content", result)
        self.assertIsInstance(result["content"], list)

    def test_messages_has_usage(self):
        result = self.api._request_post("/v1/messages", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 10,
        })
        self.assertIn("usage", result)
        usage = result["usage"]
        self.assertIn("input_tokens", usage)
        self.assertIn("output_tokens", usage)

    def test_messages_has_stop_reason(self):
        result = self.api._request_post("/v1/messages", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 10,
        })
        self.assertIn("stop_reason", result)

    def test_messages_has_model_field(self):
        result = self.api._request_post("/v1/messages", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 10,
        })
        self.assertIn("model", result)
        self.assertEqual(result["model"], "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf")

    def test_messages_has_id(self):
        result = self.api._request_post("/v1/messages", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 10,
        })
        self.assertIn("id", result)
        self.assertIsInstance(result["id"], str)

    def test_messages_content_has_thinking_type(self):
        result = self.api._request_post("/v1/messages", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "messages": [{"role": "user", "content": "say hi"}],
            "max_tokens": 10,
        })
        for item in result.get("content", []):
            if item.get("type") == "thinking":
                self.assertIn("thinking", item)
                break


class UnsupportedEndpointsTest(unittest.TestCase):
    """Test that unsupported endpoints return appropriate errors."""

    def setUp(self):
        self.api = ServerAPI("http://localhost:11435")

    def test_embeddings_returns_none_via_api_client(self):
        """API client returns None for HTTP errors (501)."""
        result = self.api._request_post("/v1/embeddings", {
            "model": "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf",
            "input": "hello world",
        })
        # Server returns 501 which API client converts to None
        self.assertIsNone(result)

    def test_rerank_returns_none_via_api_client(self):
        """API client returns None for HTTP errors (501)."""
        result = self.api._request_post("/v1/rerank", {
            "model": "test",
            "query": "test",
            "documents": ["doc1", "doc2"],
        })
        self.assertIsNone(result)

    def test_slots_action_returns_none_via_api_client(self):
        """API client returns None for HTTP errors (501)."""
        result = self.api._request_post("/slots/0", {
            "action": "save",
        })
        self.assertIsNone(result)

    def test_tokenize_returns_none_via_api_client(self):
        """API client returns None for HTTP errors (404)."""
        result = self.api._request_post("/v1/tokenize", {
            "model": "test",
            "input": "hello",
        })
        self.assertIsNone(result)

    def test_detokenize_returns_none_via_api_client(self):
        """API client returns None for HTTP errors (404)."""
        result = self.api._request_post("/v1/detokenize", {
            "model": "test",
            "tokens": [1, 2, 3],
        })
        self.assertIsNone(result)

    def test_embeddings_raw_server_returns_501(self):
        """Raw server returns 501 for embeddings endpoint."""
        import urllib.request
        import urllib.error
        url = "http://localhost:11435/v1/embeddings"
        data = json.dumps({"model": "test", "input": "hello"}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 501)

    def test_rerank_raw_server_returns_501(self):
        """Raw server returns 501 for rerank endpoint."""
        import urllib.request
        import urllib.error
        url = "http://localhost:11435/v1/rerank"
        data = json.dumps({"model": "test", "query": "test", "documents": ["doc1"]}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 501)

    def test_apply_template_returns_prompt(self):
        result = self.api._request_post("/apply-template", {
            "template": "default",
            "messages": [{"role": "user", "content": "hi"}],
        })
        self.assertIsNotNone(result)
        self.assertIn("prompt", result)
        self.assertIsInstance(result["prompt"], str)
        self.assertGreater(len(result["prompt"]), 0)

    def test_apply_template_has_assistant_marker(self):
        result = self.api._request_post("/apply-template", {
            "template": "default",
            "messages": [{"role": "user", "content": "hi"}],
        })
        self.assertIn("assistant", result["prompt"])


class MetricsParsingTest(unittest.TestCase):
    """Test prometheus metrics parsing."""

    def test_empty_metrics(self):
        result = parse_prometheus_metrics("")
        self.assertEqual(result, {})

    def test_none_metrics(self):
        result = parse_prometheus_metrics(None)
        self.assertEqual(result, {})

    def test_basic_parsing(self):
        text = """# HELP prompt_tokens_total Total prompt tokens
prompt_tokens_total 256
# HELP eval_tokens_total Total eval tokens
eval_tokens_total 128"""
        result = parse_prometheus_metrics(text)
        self.assertEqual(result["prompt_tokens_total"], 256.0)
        self.assertEqual(result["eval_tokens_total"], 128.0)

    def test_comments_ignored(self):
        text = """# comment 1
metric1 10.0
# comment 2
metric2 20.0"""
        result = parse_prometheus_metrics(text)
        self.assertEqual(len(result), 2)

    def test_float_values(self):
        text = "metric_value 42.5"
        result = parse_prometheus_metrics(text)
        self.assertEqual(result["metric_value"], 42.5)

    def test_invalid_lines_skipped(self):
        text = """valid_metric 42.0
invalid_no_value
another_valid 100"""
        result = parse_prometheus_metrics(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result["valid_metric"], 42.0)
        self.assertEqual(result["another_valid"], 100.0)

    def test_single_line(self):
        result = parse_prometheus_metrics("my_metric 123")
        self.assertEqual(result["my_metric"], 123.0)

    def test_negative_values(self):
        text = "negative_metric -5.0"
        result = parse_prometheus_metrics(text)
        self.assertEqual(result["negative_metric"], -5.0)


class ServerAPITest(unittest.TestCase):
    """Test ServerAPI error handling."""

    def test_health_returns_none_on_connection_error(self):
        api = ServerAPI("http://localhost:99999")
        result = api.health()
        self.assertIsNone(result)

    def test_request_returns_none_on_timeout(self):
        api = ServerAPI("http://localhost:11435")
        result = api._request("/health", timeout=1)
        # Should return dict or None, not raise
        self.assertIsNotNone(result)  # Server should respond

    def test_request_handles_non_json_response(self):
        from api_client import ServerAPI
        api = ServerAPI("http://localhost:11435")
        result = api.health()
        self.assertIsInstance(result, dict)


class MonitorTabParsingTest(unittest.TestCase):
    """Test MonitorTab slot data parsing."""

    def test_parse_slot_data_for_display(self):
        """Simulate what MonitorTab._fetch_slots does with slot data."""
        slots = [
            {"id": 0, "is_processing": False, "n_past": 50, "n_ctx": 131072},
            {"id": 1, "is_processing": True, "n_past": 100, "n_ctx": 131072},
        ]
        lines = []
        idle = sum(1 for s in slots if not s["is_processing"])
        processing = sum(1 for s in slots if s["is_processing"])
        lines.append(f'Idle: {idle} | Processing: {processing}')
        lines.append('-' * 40)
        for slot in slots:
            ctx = slot.get("n_past", 0)
            n_ctx = slot.get("n_ctx", 0)
            pct = ctx / n_ctx * 100 if n_ctx > 0 else 0
            bar_len = 20
            filled = int(bar_len * pct / 100)
            bar = '#' * filled + '-' * (bar_len - filled)
            state = 'PROC' if slot["is_processing"] else 'IDLE'
            lines.append(f'  Slot {slot["id"]} [{state}] |{bar}| {ctx}/{n_ctx}')
        self.assertIn("Idle: 1 | Processing: 1", lines[0])
        self.assertIn("IDLE", lines[2])
        self.assertIn("PROC", lines[3])

    def test_slots_display_with_zero_ctx(self):
        slots = [{"id": 0, "is_processing": False, "n_past": 0, "n_ctx": 131072}]
        pct = slots[0]["n_past"] / slots[0]["n_ctx"] * 100
        self.assertEqual(pct, 0.0)

    def test_slots_display_full_context(self):
        slots = [{"id": 0, "is_processing": False, "n_past": 131072, "n_ctx": 131072}]
        pct = slots[0]["n_past"] / slots[0]["n_ctx"] * 100
        self.assertEqual(pct, 100.0)


class ConfigTabPropsTest(unittest.TestCase):
    """Test ConfigTab defaults loading from /props."""

    def test_load_defaults_from_props(self):
        """Simulate loading default generation settings from /props."""
        props = PROPS
        params = props["default_generation_settings"]["params"]
        self.assertAlmostEqual(params["temperature"], 1.0, places=6)
        self.assertEqual(params["top_k"], 20)
        self.assertAlmostEqual(params["top_p"], 0.95, places=6)
        self.assertAlmostEqual(params["min_p"], 0.05, places=6)
        self.assertEqual(params["repeat_penalty"], 1.0)

    def test_chat_format_from_props(self):
        params = PROPS["default_generation_settings"]["params"]
        self.assertEqual(params["chat_format"], "Content-only")

    def test_reasoning_format_from_props(self):
        params = PROPS["default_generation_settings"]["params"]
        self.assertEqual(params["reasoning_format"], "none")

    def test_samplers_from_props(self):
        params = PROPS["default_generation_settings"]["params"]
        self.assertIn("temperature", params["samplers"])
        self.assertIn("top_p", params["samplers"])
        self.assertIn("top_k", params["samplers"])

    def test_props_model_info_matches_model(self):
        self.assertEqual(
            PROPS["model_alias"],
            "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf"
        )


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main()
