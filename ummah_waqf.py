from fastapi import APIRouter, Depends, HTTPException, Query

from api.schemas import WaqfCreate
from api.security import get_current_user_id_from_key
from core.dependencies import get_mubarak_ai_instance
from core.main_app import MubarakAI
from models import ModuleType

router = APIRouter(
    tags=["Ummah Waqf"],
)


@router.get("/waqfs")
async def list_available_waqfs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Получить список всех доступных вакфов."""
    request = {
        "module": ModuleType.UMMAH_WAQF.value, "type": "list_waqfs",
        "skip": skip, "limit": limit
    }
    result = await mubarakai.process_request("system", request)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Не удалось получить список вакфов."))
    return result


@router.post("/waqfs")
async def create_new_waqf(
    waqf_data: WaqfCreate,
    user_id: str = Depends(get_current_user_id_from_key),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Создает новый вакф от имени аутентифицированного пользователя."""
    request = {"module": ModuleType.UMMAH_WAQF.value, "type": "create_waqf", **waqf_data.model_dump()}
    result = await mubarakai.process_request(user_id, request)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Не удалось создать вакф."))
    return result