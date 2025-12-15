from fastapi import APIRouter, Depends

from api.schemas import KnowledgeSessionCreate
from core.dependencies import get_mubarak_ai_instance
from core.main_app import MubarakAI
from core.exceptions import DetailedHTTPException
from models import ModuleType

router = APIRouter(tags=["Ar-Rihla"])


@router.post("/ar-rihla/sessions")
async def create_knowledge_session(user_id: str, session_data: KnowledgeSessionCreate, mubarakai: MubarakAI = Depends(get_mubarak_ai_instance)):
    """Создать новую сессию знаний (требует ID пользователя)."""
    request = {"module": ModuleType.AR_RIHLA.value, "type": "create_knowledge_session", "topic": session_data.topic, "time": session_data.time}
    result = await mubarakai.process_request(user_id, request)
    if not result.get("success"):
        raise DetailedHTTPException(status_code=400, error_code="SESSION_CREATION_FAILED", detail=result.get("error", "Не удалось создать сессию."))
    return result