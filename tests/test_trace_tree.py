from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Chạy trong subprocess vì Langfuse client là singleton toàn tiến trình. Span được
# xuất ra InMemorySpanExporter nên test không cần key thật và không gọi mạng.
TRACE_SCRIPT = textwrap.dedent(
    """
    import json
    import sys

    from langfuse import Langfuse
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    client = Langfuse(
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        base_url="http://127.0.0.1:9",
        tracer_provider=TracerProvider(),
        span_exporter=exporter,
    )

    from app import agent as agent_module
    from app.incidents import STATE

    agent_module.tracing_enabled = lambda: False  # prompt local, không fetch Langfuse
    agent = agent_module.LabAgent()
    message = "Refund? mail student@vinuni.edu.vn phone 0987654321"
    result = agent.run(
        user_id="u01", feature="qa", session_id="s01", message=message,
        correlation_id="req-1a2b3c4d",
    )
    STATE["tool_fail"] = True
    try:
        agent.run(
            user_id="u02", feature="qa", session_id="s02", message="monitoring",
            correlation_id="req-0badc0de",
        )
    except RuntimeError:
        pass
    client.flush()

    spans = exporter.get_finished_spans()
    names = {span.context.span_id: span.name for span in spans}
    json.dump(
        {
            "result": {"cost_usd": result.cost_usd, "tokens_in": result.tokens_in,
                       "tokens_out": result.tokens_out},
            "spans": [
                {
                    "name": span.name,
                    "trace_id": format(span.context.trace_id, "032x"),
                    "parent": names.get(span.parent.span_id) if span.parent else None,
                    "attributes": {key: value if isinstance(value, (str, int, float, bool))
                                   else list(value) for key, value in span.attributes.items()},
                }
                for span in spans
            ],
        },
        sys.stdout,
    )
    """
)


@pytest.fixture(scope="module")
def captured() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("LANGFUSE_")}
    completed = subprocess.run(
        [sys.executable, "-c", TRACE_SCRIPT],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _spans_for(captured: dict, correlation_id: str) -> list[dict]:
    key = "langfuse.trace.metadata.correlation_id"
    return [span for span in captured["spans"] if span["attributes"].get(key) == correlation_id]


def test_trace_has_root_retrieval_and_generation_without_raw_pii(captured: dict) -> None:
    spans = _spans_for(captured, "req-1a2b3c4d")
    by_name = {span["name"]: span for span in spans}

    assert set(by_name) == {"lab-agent-run", "rag-retrieve", "llm-generate"}
    assert len({span["trace_id"] for span in spans}) == 1

    root, retrieval, generation = by_name["lab-agent-run"], by_name["rag-retrieve"], by_name["llm-generate"]
    assert root["parent"] is None
    assert root["attributes"]["langfuse.observation.type"] == "agent"
    assert retrieval["parent"] == "lab-agent-run"
    assert retrieval["attributes"]["langfuse.observation.type"] == "retriever"
    assert generation["parent"] == "lab-agent-run"
    assert generation["attributes"]["langfuse.observation.type"] == "generation"

    gen_attrs = generation["attributes"]
    usage = json.loads(gen_attrs["langfuse.observation.usage_details"])
    cost = json.loads(gen_attrs["langfuse.observation.cost_details"])
    result = captured["result"]
    assert gen_attrs["langfuse.observation.model.name"] == "claude-sonnet-4-5"
    assert usage == {
        "input": result["tokens_in"],
        "output": result["tokens_out"],
        "total": result["tokens_in"] + result["tokens_out"],
    }
    assert cost["total"] == result["cost_usd"]
    assert "langfuse.observation.completion_start_time" in gen_attrs

    serialized = json.dumps(spans)
    assert "student@vinuni.edu.vn" not in serialized
    assert "0987654321" not in serialized


def test_failed_retrieval_is_recorded_as_error_on_retriever_span(captured: dict) -> None:
    spans = _spans_for(captured, "req-0badc0de")
    by_name = {span["name"]: span for span in spans}

    assert "llm-generate" not in by_name
    retrieval = by_name["rag-retrieve"]
    assert retrieval["attributes"]["langfuse.observation.level"] == "ERROR"
    assert "Vector store timeout" in retrieval["attributes"]["langfuse.observation.status_message"]
