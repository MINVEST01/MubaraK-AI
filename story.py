from pydantic import BaseModel


class StoryResponse(BaseModel):
    """Схема для ответа 'История дня'."""
    title: str
    story_text: str
    lesson: str
    source: str | None = None