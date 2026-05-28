from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.clients.model_client import build_model_client
from app.core.config import get_settings
from app.models.evaluation import EvaluationDetail
from app.runners.evaluation_runner import EvaluationRunner
from app.services.evaluation_service import CreateEvaluationResult, EvaluationService
from app.storage.evaluation_store import EvaluationStore


router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


def get_store() -> EvaluationStore:
    return EvaluationStore(get_settings().data_dir / "evaluations")


def get_service() -> EvaluationService:
    return EvaluationService(get_store())


def get_runner() -> EvaluationRunner:
    settings = get_settings()
    return EvaluationRunner(
        store=get_store(),
        model_client=build_model_client(settings),
    )


@router.post("")
async def create_evaluation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    service: EvaluationService = Depends(get_service),
    runner: EvaluationRunner = Depends(get_runner),
) -> CreateEvaluationResult:
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    result = service.create_or_reuse(filename=file.filename or "upload.bin", file_bytes=payload)
    if not result.dedupe_hit:
        background_tasks.add_task(runner.run, result.evaluation_id)
    return result


@router.get("/{evaluation_id}")
def get_evaluation(
    evaluation_id: str,
    service: EvaluationService = Depends(get_service),
) -> EvaluationDetail:
    try:
        return service.get_detail(evaluation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evaluation not found.") from exc


@router.post("/{evaluation_id}/retry")
def retry_evaluation(
    background_tasks: BackgroundTasks,
    evaluation_id: str,
    service: EvaluationService = Depends(get_service),
    runner: EvaluationRunner = Depends(get_runner),
) -> CreateEvaluationResult:
    try:
        result = service.retry(evaluation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evaluation not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not result.dedupe_hit:
        background_tasks.add_task(runner.run, result.evaluation_id)
    return result
