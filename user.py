from pydantic import BaseModel, Field
from datetime import timedelta


class UserBlockRequest(BaseModel):
    """Схема для запроса на блокировку пользователя."""
    duration: timedelta = Field(
        ...,
        description="Длительность блокировки. Например: 'P1DT12H' (1 день и 12 часов)."
    )