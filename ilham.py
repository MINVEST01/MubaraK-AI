from pydantic import BaseModel


class IlhamRequest(BaseModel):
    """Схема запроса для Ilham-AI."""
    prompt: str  # Например: "Я чувствую грусть", "Мне нужна мотивация", "Благодарность"
    conversation_id: str | None = None # Для поддержания контекста диалога


class IlhamResponse(BaseModel):
    """Схема ответа от Ilham-AI."""
    text: str
    source: str | None = None
    commentary: str | None = None
    prompt_used: str
    response_type: str = "inspiration"
    suggestions: list[str] | None = None
    conversation_id: str | None = None # Возвращается для продолжения диалога