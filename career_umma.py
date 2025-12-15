from typing import Optional

from opentelemetry import trace
from fastapi import APIRouter, Depends, HTTPException, Query

from api.schemas import JobApplicationUpdate, JobPostCreate
from api.security import get_current_user_id_from_key
from core.dependencies import get_mubarak_ai_instance
from core.exceptions import DetailedHTTPException
from core.main_app import MubarakAI
from models import ModuleType

# Получаем трейсер для текущего модуля. Лучшая практика - называть его по имени модуля.
tracer = trace.get_tracer(__name__)

router = APIRouter(
    tags=["Career Umma"],
)


@router.post("/jobs")
async def post_new_job(
    job_data: JobPostCreate,
    user_id: str = Depends(get_current_user_id_from_key),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Публикует новую вакансию от имени аутентифицированного пользователя."""
    # Создаем кастомный спан для измерения времени выполнения бизнес-логики
    with tracer.start_as_current_span("process_new_job_posting") as span:
        # Добавляем полезные атрибуты в спан для лучшего контекста
        span.set_attribute("mubarak.module", ModuleType.CAREER_UMMA.value)
        span.set_attribute("mubarak.user_id", user_id)
        span.set_attribute("mubarak.job.title", job_data.title)
        span.set_attribute("mubarak.job.location", job_data.location)

        # Добавляем событие в спан
        span.add_event("Начало обработки запроса на публикацию вакансии")

        request = {
            "module": ModuleType.CAREER_UMMA.value,
            "type": "post_job",
            **job_data.model_dump(),
        }
        result = await mubarakai.process_request(user_id, request)

        span.add_event("Запрос обработан, получен результат", attributes={"success": result.get("success")})

        if not result.get("success"):
            raise DetailedHTTPException(
                status_code=400,
                error_code="JOB_POSTING_FAILED",
                detail=result.get("error", "Не удалось опубликовать вакансию.")
            )
        return result


@router.get("/jobs")
async def search_jobs(
    query: Optional[str] = Query(None, description="Ключевое слово для поиска по названию или описанию"),
    location: Optional[str] = Query(None, description="Город для фильтрации вакансий"),
    level: Optional[str] = Query(None, description="Требуемый уровень (например, junior, middle, senior)"),
    skip: int = Query(0, ge=0, description="Сколько записей пропустить"),
    limit: int = Query(20, ge=1, le=100, description="Максимальное количество записей на странице"),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Ищет открытые вакансии."""
    request = {
        "module": ModuleType.CAREER_UMMA.value,
        "type": "search_jobs",
        "query": query, "location": location, "level": level,
        "skip": skip, "limit": limit,
    }
    result = await mubarakai.process_request("system", request) # Поиск публичен
    if not result.get("success"):
        raise DetailedHTTPException(
            status_code=500,
            error_code="JOB_SEARCH_FAILED",
            detail=result.get("error", "Ошибка при поиске вакансий.")
        )
    return result


@router.post("/jobs/{vacancy_id}/apply")
async def apply_for_job(
    vacancy_id: int,
    user_id: str = Depends(get_current_user_id_from_key),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Позволяет аутентифицированному пользователю откликнуться на вакансию."""
    request = {
        "module": ModuleType.CAREER_UMMA.value,
        "type": "apply_for_job",
        "vacancy_id": vacancy_id,
    }
    result = await mubarakai.process_request(user_id, request)
    if not result.get("success"):
        raise DetailedHTTPException(
            status_code=400,
            error_code="JOB_APPLICATION_FAILED",
            detail=result.get("error") or result.get("message")
        )
    return result


@router.get("/jobs/{vacancy_id}/applications")
async def get_job_applications(
    vacancy_id: int,
    user_id: str = Depends(get_current_user_id_from_key),
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Получает список откликов на вакансию. Доступно только для автора вакансии."""
    request = {
        "module": ModuleType.CAREER_UMMA.value, "type": "get_job_applications",
        "vacancy_id": vacancy_id, "skip": skip, "limit": limit,
    }
    result = await mubarakai.process_request(user_id, request)
    if not result.get("success"):
        raise DetailedHTTPException(
            status_code=403,
            error_code="ACCESS_DENIED",
            detail=result.get("error") or result.get("message")
        )
    return result


# ... и так далее для остальных эндпоинтов Career Umma ...