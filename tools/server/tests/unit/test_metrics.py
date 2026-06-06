import pytest
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
from prometheus_client.openmetrics.parser import text_string_to_metric_families
from utils import *

server = ServerPreset.tinyllama2()


@pytest.fixture(autouse=True)
def create_server():
    global server
    server = ServerPreset.tinyllama2()


# ── helpers ────────────────────────────────────────────────────────────────────

def get_metrics_text(srv: ServerProcess) -> str:
    """Return the raw Prometheus text from GET /metrics."""
    res = srv.make_request("GET", "/metrics")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.body}"
    assert isinstance(res.body, str), "Expected plain-text body"
    return res.body


def parse_metrics(text: str) -> dict:
    """
    Parse Prometheus exposition text into a flat dict:
      { metric_name: {label_frozenset: value, ...}, ... }
    where unlabeled metrics have an empty frozenset key.
    """
    result = {}
    for family in text_string_to_metric_families(text):
        samples = {}
        for sample in family.samples:
            key = frozenset(sample.labels.items()) if sample.labels else frozenset()
            samples[key] = sample.value
        result[family.name] = samples
    return result


def get_scalar(metrics: dict, name: str) -> float:
    """Return the scalar (unlabeled) value of a metric."""
    assert name in metrics, f"Metric {name!r} not found; available: {sorted(metrics)}"
    assert frozenset() in metrics[name], f"Metric {name!r} has no unlabeled value"
    return metrics[name][frozenset()]


def get_slot(metrics: dict, name: str, slot_id: int) -> float:
    """Return the per-slot value of a labeled metric."""
    assert name in metrics, f"Metric {name!r} not found"
    key = frozenset({("id_slot", str(slot_id))})
    assert key in metrics[name], f"Metric {name!r} has no slot {slot_id} label"
    return metrics[name][key]


# ── tests ──────────────────────────────────────────────────────────────────────

def test_metrics_disabled_by_default():
    """Without --metrics the endpoint must return 501."""
    global server
    server.server_metrics = False
    server.start()
    res = server.make_request("GET", "/metrics")
    assert res.status_code == 501
    assert "error" in res.body

    res = server.make_request("POST", "/metrics", data={"reset": True})
    assert res.status_code == 501
    assert "error" in res.body


def test_metrics_enabled_returns_prometheus_text():
    """With --metrics, GET /metrics returns valid Prometheus exposition text."""
    global server
    server.server_metrics = True
    server.start()

    text = get_metrics_text(server)

    # Must contain at least one known metric family.
    assert "llamacpp:prompt_tokens_total" in text
    assert "llamacpp:tokens_predicted_total" in text
    assert "llamacpp:n_decode_total" in text

    # Must include Process-Start-Time-Unix header.
    res = server.make_request("GET", "/metrics")
    assert "Process-Start-Time-Unix" in res.headers
    start_time = int(res.headers["Process-Start-Time-Unix"])
    assert start_time > 0

    # Must parse cleanly as Prometheus text.
    metrics = parse_metrics(text)
    assert "llamacpp:prompt_tokens_total" in metrics


def test_metrics_initial_counters_are_zero():
    """Right after start, before any completion, all counters are 0."""
    global server
    server.server_metrics = True
    server.start()

    metrics = parse_metrics(get_metrics_text(server))

    assert get_scalar(metrics, "llamacpp:prompt_tokens_total")    == 0
    assert get_scalar(metrics, "llamacpp:tokens_predicted_total") == 0
    assert get_scalar(metrics, "llamacpp:n_decode_total")         == 0


def test_metrics_increase_after_completion():
    """After a completion request, prompt and generation counters must be > 0."""
    global server
    server.server_metrics = True
    server.start()

    # Run a short completion.
    res = server.make_request("POST", "/completion", data={
        "prompt":      "Tell me a short story",
        "n_predict":   8,
        "temperature": 0.0,
    })
    assert res.status_code == 200

    metrics = parse_metrics(get_metrics_text(server))

    assert get_scalar(metrics, "llamacpp:prompt_tokens_total")    > 0
    assert get_scalar(metrics, "llamacpp:tokens_predicted_total") > 0
    assert get_scalar(metrics, "llamacpp:n_decode_total")         > 0
    assert get_scalar(metrics, "llamacpp:n_tokens_max")           > 0


def test_metrics_per_slot_labels_present():
    """Per-slot metrics must have an 'id_slot' label for each configured slot."""
    global server
    server.server_metrics = True
    server.n_slots = 2
    server.start()

    # Trigger one completion so per-slot counters are populated.
    res = server.make_request("POST", "/completion", data={
        "prompt":      "Once",
        "n_predict":   4,
        "temperature": 0.0,
        "id_slot":     0,
    })
    assert res.status_code == 200

    metrics = parse_metrics(get_metrics_text(server))

    # Both slots must appear in per-slot families.
    for slot_id in range(server.n_slots):
        key = frozenset({("id_slot", str(slot_id))})
        assert key in metrics.get("llamacpp:slot_prompt_tokens_processed", {}), \
            f"Missing id_slot={slot_id} in slot_prompt_tokens_processed"
        assert key in metrics.get("llamacpp:slot_tokens_predicted", {}), \
            f"Missing id_slot={slot_id} in slot_tokens_predicted"

    # Slot 0 must have non-zero pp tokens after our completion.
    assert get_slot(metrics, "llamacpp:slot_prompt_tokens_processed", 0) > 0


def test_metrics_reset_global():
    """POST /metrics with {reset: true} must zero the global counters."""
    global server
    server.server_metrics = True
    server.start()

    # Generate some traffic.
    res = server.make_request("POST", "/completion", data={
        "prompt":      "Hello world",
        "n_predict":   4,
        "temperature": 0.0,
    })
    assert res.status_code == 200

    before = parse_metrics(get_metrics_text(server))
    assert get_scalar(before, "llamacpp:prompt_tokens_total") > 0

    # Reset.
    reset_res = server.make_request("POST", "/metrics", data={"reset": True})
    assert reset_res.status_code == 200
    assert reset_res.body.get("status") == "ok"

    after = parse_metrics(get_metrics_text(server))
    assert get_scalar(after, "llamacpp:prompt_tokens_total")    == 0
    assert get_scalar(after, "llamacpp:tokens_predicted_total") == 0
    assert get_scalar(after, "llamacpp:n_decode_total")         == 0

    # High-water mark must NOT be reset.
    assert get_scalar(after, "llamacpp:n_tokens_max") > 0


def test_metrics_reset_without_body_is_noop():
    """POST /metrics with no body (or empty body) must not crash and return 200."""
    global server
    server.server_metrics = True
    server.start()

    res = server.make_request("POST", "/completion", data={
        "prompt": "Hi", "n_predict": 2, "temperature": 0.0,
    })
    assert res.status_code == 200

    before = parse_metrics(get_metrics_text(server))
    n_before = get_scalar(before, "llamacpp:prompt_tokens_total")
    assert n_before > 0

    # POST with reset=false → should be a no-op.
    r = server.make_request("POST", "/metrics", data={"reset": False})
    assert r.status_code == 200

    after = parse_metrics(get_metrics_text(server))
    assert get_scalar(after, "llamacpp:prompt_tokens_total") == n_before


def test_metrics_prometheus_format_valid():
    """Verify that HELP/TYPE lines appear exactly once per metric family."""
    global server
    server.server_metrics = True
    server.n_slots = 2
    server.start()

    text = get_metrics_text(server)

    # Count occurrences of each # TYPE line — must be exactly 1 per family.
    type_counts: dict[str, int] = {}
    for line in text.splitlines():
        if line.startswith("# TYPE "):
            name = line.split()[2]
            type_counts[name] = type_counts.get(name, 0) + 1

    for name, count in type_counts.items():
        assert count == 1, (
            f"Metric family {name!r} has {count} # TYPE lines; expected exactly 1"
        )
