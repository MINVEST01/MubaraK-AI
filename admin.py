from fastapi import APIRouter, Depends, Query

from api.security import require_role
from core.dependencies import get_mubarak_ai_instance
from core.main_app import MubarakAI
from models import UserRole

router = APIRouter(
    tags=["Admin"],
)


@router.get("/users")
async def list_all_users(
    user_id: str = Depends(require_role(UserRole.ADMIN)),
    skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Получить список всех пользователей (только для администраторов)."""
    users_page, total_count = await mubarakai.get_all_users(skip=skip, limit=limit)
    return {"total_count": total_count, "users": users_page}