from pydantic import BaseModel


class PushTokenUpdate(BaseModel):
    """Схема для обновления push-токена пользователя."""
    token: str