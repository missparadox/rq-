"""Minimal API smoke tests for the backend evaluation flow."""

from fastapi.testclient import TestClient

from conftest import configure_runtime_env, import_app_main_module


VALID_REQUIREMENTS_CSV = (
    "OR需求编号,OR需求名称*,OR需求描述*,需求分类,DR需求编号,DR需求名称*,DR需求描述*\n"
    "D1,N,D,功能,DR1,DN,DD\n"
).encode("utf-8")


def _create_client(tmp_path, monkeypatch) -> TestClient:
    configure_runtime_env(
        monkeypatch,
        data_dir=str(tmp_path),
        debug_fallback_enabled=True,
    )
    return TestClient(import_app_main_module().create_app())


def test_create_and_get_evaluation_detail(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)

    create = client.post(
        "/api/evaluations",
        files={
            "file": (
                "requirements.csv",
                VALID_REQUIREMENTS_CSV,
                "text/csv",
            )
        },
    )
    evaluation_id = create.json()["evaluation_id"]
    detail = client.get(f"/api/evaluations/{evaluation_id}")

    assert create.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["evaluation_id"] == evaluation_id
    assert detail.json()["status"] == "succeeded"
    assert detail.json()["report_markdown"].startswith("# 需求评估报告")


def test_retry_evaluation_creates_new_pending_task(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)

    create = client.post(
        "/api/evaluations",
        files={
            "file": (
                "requirements.csv",
                VALID_REQUIREMENTS_CSV,
                "text/csv",
            )
        },
    )
    original_evaluation_id = create.json()["evaluation_id"]
    metadata_path = tmp_path / "evaluations" / original_evaluation_id / "metadata.json"
    metadata = __import__("json").loads(metadata_path.read_text(encoding="utf-8"))
    metadata["status"] = "failed"
    metadata["error_message"] = "forced failure"
    metadata_path.write_text(__import__("json").dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    retry = client.post(f"/api/evaluations/{original_evaluation_id}/retry")

    assert retry.status_code == 200
    assert retry.json()["evaluation_id"] != original_evaluation_id


def test_get_evaluation_returns_404_for_missing_id(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)

    response = client.get("/api/evaluations/eval_missing")

    assert response.status_code == 404
