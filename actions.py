from fastapi import APIRouter

from api.schemas import GenericRequest
from core.dependencies import get_mubarak_ai_instance
from core.main_app import MubarakAI

router = APIRouter(tags=["Actions"])


@router.post("/users/{user_id}/request")
async def handle_user_request(user_id: str, request: GenericRequest, mubarakai: MubarakAI = Depends(get_mubarak_ai_instance)):
    """Универсальный эндпоинт для обработки запросов к модулям."""
    full_request = {"module": request.module, "type": request.type, **(request.data or {})}
    result = await mubarakai.process_request(user_id, full_request)
    if "error" in result and result.get("success") is False:
        raise DetailedHTTPException(status_code=400, error_code="REQUEST_FAILED", detail=result["error"])
    return result