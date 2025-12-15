from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_mubarak_ai_instance
from core.main_app import MubarakAI
from core.exceptions import DetailedHTTPException
from models import ModuleType

router = APIRouter(
    tags=["Baitul Hikma"],
)


@router.get("/projects/{project_id}")
async def get_project_details(
    project_id: str,
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance)
):
    """Получить детали конкретного проекта."""
    request = {"module": ModuleType.BAITUL_HIKMA.value, "type": "get_project_details", "project_id": project_id}
    result = await mubarakai.modules[ModuleType.BAITUL_HIKMA].process_request("system", request)
    if not result.get("success"):
        # Используем наше новое, более детальное исключение
        raise DetailedHTTPException(
            status_code=404,
            error_code="PROJECT_NOT_FOUND",
            detail=result.get("error", "Проект с указанным ID не найден."),
            project_id=project_id
        )
    return result