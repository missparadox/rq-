"""Minimal smoke tests for storage safety and report detail reads."""

import json
from pathlib import Path

from app.storage.evaluation_store import EvaluationStore


def test_create_evaluation_normalizes_filename_to_block_traversal(tmp_path: Path) -> None:
    store = EvaluationStore(tmp_path)

    record = store.create_evaluation(
        evaluation_id="eval_002",
        filename="../outside.txt",
        file_bytes=b"safe",
    )

    evaluation_dir = tmp_path / "eval_002"
    assert record["original_file_path"] == evaluation_dir / "outside.txt"
    assert record["original_file_path"].parent == evaluation_dir
    assert record["original_file_path"].read_bytes() == b"safe"
    metadata = json.loads(record["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["filename"] == "outside.txt"


def test_read_detail_includes_report_markdown_when_report_exists(tmp_path: Path) -> None:
    store = EvaluationStore(tmp_path)
    store.create_evaluation(evaluation_id="eval_001", filename="requirements.csv", file_bytes=b"abc")
    report_path = tmp_path / "eval_001" / "report.md"
    report_path.write_text("# Report\n", encoding="utf-8")
    store.update_metadata(
        "eval_001",
        {
            "status": "succeeded",
            "report_path": str(report_path),
            "token_budget_summary": {"packet_count": 1},
        },
    )

    detail = store.read_detail("eval_001")

    assert detail.status == "succeeded"
    assert detail.report_markdown == "# Report\n"
    assert detail.token_budget_summary == {"packet_count": 1}
