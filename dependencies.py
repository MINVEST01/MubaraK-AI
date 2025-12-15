from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from core.main_app import MubarakAI


def get_mubarak_ai_instance(request: Request) -> "MubarakAI":
    """Зависимость для получения экземпляра MubarakAI из состояния приложения."""
    return request.app.state.mubarakai