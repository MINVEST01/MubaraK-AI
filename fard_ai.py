from fastapi import APIRouter, Depends

from core.dependencies import get_mubarak_ai_instance
from core.main_app import MubarakAI
from core.exceptions import DetailedHTTPException
from models import ModuleType

router = APIRouter(tags=["Fard-AI"])


@router.get("/users/{user_id}/fard-ai/learning-progress")
async def get_user_learning_progress(user_id: str, mubarakai: MubarakAI = Depends(get_mubarak_ai_instance)):
    """Получить прогресс обучения пользователя."""
    request = {"module": ModuleType.FARD_AI.value, "type": "get_learning_progress"}
    result = await mubarakai.process_request(user_id, request)
    if not result.get("success"):
        raise DetailedHTTPException(status_code=404, error_code="PROGRESS_NOT_FOUND", detail=result.get("error", "Не удалось получить прогресс."))
    return result