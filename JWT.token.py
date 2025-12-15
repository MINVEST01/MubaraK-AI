from pydantic import BaseModel


class Token(BaseModel):
    """Схема для ответа с JWT-токеном."""
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    """
    Схема для данных, хранящихся внутри JWT-токена (полезная нагрузка).
    """
    sub: str | None = None