from __future__ import annotations

"""Minimal smoke tests for dedupe rules and runner success/failure behavior."""

from pathlib import Path
from unittest.mock import Mock

from app.clients.model_client import StaticModelClient
from app.runners.evaluation_runner import (
    SPLIT_REVIEW_INSTRUCTIONS,
    EvaluationRunner,
    build_split_review_artifacts,
)
from app.services.evaluation_service import EvaluationService
from app.storage.evaluation_store import EvaluationStore


VALID_REQUIREMENTS_CSV = (
    "OR需求编号,OR需求名称*,OR需求描述*,需求分类,DR需求编号,DR需求名称*,DR需求描述*\n"
    "D1,N,D,功能,DR1,DN,DD\n"
).encode("utf-8")

TWO_OR_REQUIREMENTS_CSV = (
    "OR需求编号,OR需求名称*,OR需求描述*,需求分类,DR需求编号,DR需求名称*,DR需求描述*\n"
    "D1,N1,D1,功能,DR1,DN1,DD1\n"
    "D2,N2,D2,功能,DR2,DN2,DD2\n"
).encode("utf-8")


class CountingStaticModelClient(StaticModelClient):
    def __init__(self) -> None:
        self.calls = 0
        self.inputs: list[str] = []

    def generate_text(self, *, instructions: str, input_text: str) -> str:
        self.calls += 1
        self.inputs.append(input_text)
        return super().generate_text(instructions=instructions, input_text=input_text)


def test_create_reuses_existing_evaluation_when_dedupe_key_matches(tmp_path: Path) -> None:
    service = EvaluationService(store=EvaluationStore(tmp_path))

    first = service.create_or_reuse(filename="requirements.csv", file_bytes=b"abc")
    second = service.create_or_reuse(filename="requirements.csv", file_bytes=b"abc")

    assert second.evaluation_id == first.evaluation_id
    assert second.dedupe_hit is True


def test_create_makes_new_evaluation_when_model_provider_changes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    monkeypatch.delenv("REQUIREMENTS_EVALUATOR_DEBUG_FALLBACK", raising=False)
    first = EvaluationService(store=EvaluationStore(tmp_path)).create_or_reuse(
        filename="requirements.csv",
        file_bytes=b"abc",
    )

    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv("ZHIPU_MODEL", "zhipu-model")
    second = EvaluationService(store=EvaluationStore(tmp_path)).create_or_reuse(
        filename="requirements.csv",
        file_bytes=b"abc",
    )

    assert second.evaluation_id != first.evaluation_id
    assert second.dedupe_hit is False


def test_runner_writes_report_and_marks_success(tmp_path: Path) -> None:
    store = EvaluationStore(tmp_path)
    store.create_evaluation(
        evaluation_id="eval_001",
        filename="requirements.csv",
        file_bytes=VALID_REQUIREMENTS_CSV,
    )

    EvaluationRunner(store=store, model_client=StaticModelClient()).run("eval_001")

    metadata = store.read_metadata("eval_001")
    assert metadata["status"] == "succeeded"
    assert (tmp_path / "eval_001" / "report.md").exists()
    assert (tmp_path / "eval_001" / "token-budget.json").exists()


def test_runner_marks_evaluation_failed_when_packet_building_raises(tmp_path: Path, monkeypatch) -> None:
    store = EvaluationStore(tmp_path)
    store.create_evaluation(
        evaluation_id="eval_001",
        filename="requirements.csv",
        file_bytes=VALID_REQUIREMENTS_CSV,
    )
    monkeypatch.setattr(
        "app.runners.evaluation_runner.build_split_review_artifacts",
        Mock(side_effect=RuntimeError("boom")),
    )

    try:
        EvaluationRunner(store=store, model_client=StaticModelClient()).run("eval_001")
    except RuntimeError:
        pass
    else:
        raise AssertionError("runner.run() did not re-raise packet builder failure")

    metadata = store.read_metadata("eval_001")
    assert metadata["status"] == "failed"
    assert metadata["error_message"] == "boom"


def test_runner_resumes_from_existing_partial_results(tmp_path: Path) -> None:
    store = EvaluationStore(tmp_path)
    store.create_evaluation(
        evaluation_id="eval_001",
        filename="requirements.csv",
        file_bytes=TWO_OR_REQUIREMENTS_CSV,
    )
    evaluation_dir = tmp_path / "eval_001"
    artifacts = build_split_review_artifacts(
        input_path=evaluation_dir / "requirements.csv",
        artifact_dir=evaluation_dir,
    )
    packets = sorted(artifacts["packets_dir"].glob("or-*.md"))
    first_packet = packets[0]
    first_result = StaticModelClient().generate_text(
        instructions=SPLIT_REVIEW_INSTRUCTIONS,
        input_text=first_packet.read_text(encoding="utf-8"),
    )
    (artifacts["results_dir"] / first_packet.name).write_text(first_result, encoding="utf-8")

    client = CountingStaticModelClient()
    EvaluationRunner(store=store, model_client=client).run("eval_001")

    assert client.calls == 1
    assert "[SKILL]" not in client.inputs[0]
    assert "[SCORING_ANCHORS]" not in client.inputs[0]
    assert "## 评分与输出约束" in client.inputs[0]
    assert "仅输出下方 tagged 结果" in client.inputs[0]
    assert all((artifacts["results_dir"] / packet.name).exists() for packet in packets)
