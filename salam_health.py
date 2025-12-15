from fastapi import APIRouter, Depends, HTTPException

from api.schemas import FitnessGoalCreate, FitnessGoalUpdate
from api.security import get_current_user_id_from_key
from core.dependencies import get_mubarak_ai_instance
from core.main_app import MubarakAI
from models import ModuleType

router = APIRouter(
    tags=["Salam Health"],
)


@router.post("/goals")
async def set_fitness_goal(
    goal_data: FitnessGoalCreate,
    user_id: str = Depends(get_current_user_id_from_key),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Устанавливает новую фитнес-цель для аутентифицированного пользователя."""
    request = {
        "module": ModuleType.SALAM_HEALTH.value,
        "type": "set_fitness_goal",
        **goal_data.model_dump(),
    }
    result = await mubarakai.process_request(user_id, request)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Не удалось установить цель."))
    return result


@router.get("/goals")
async def get_fitness_goals(
    user_id: str = Depends(get_current_user_id_from_key),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Получает список всех фитнес-целей аутентифицированного пользователя."""
    request = {
        "module": ModuleType.SALAM_HEALTH.value,
        "type": "get_fitness_goals",
    }
    result = await mubarakai.process_request(user_id, request)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Не удалось получить цели."))
    return result


@router.put("/goals/{goal_id}/progress")
async def update_fitness_goal_progress(
    goal_id: int,
    goal_update: FitnessGoalUpdate,
    user_id: str = Depends(get_current_user_id_from_key),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Обновляет прогресс по конкретной фитнес-цели."""
    request = {
        "module": ModuleType.SALAM_HEALTH.value,
        "type": "update_goal_progress",
        "goal_id": goal_id,
        "progress_value": goal_update.progress_value,
    }
    result = await mubarakai.process_request(user_id, request)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or result.get("message"))
    return result