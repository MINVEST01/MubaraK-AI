from pydantic import BaseModel, HttpUrl
from enum import Enum


class VideoStyle(str, Enum):
    """Перечисление доступных стилей для генерации видео."""
    MINIMALISM = "minimalism"
    CALLIGRAPHY = "calligraphy"
    NATURE = "nature"


class DuaGenerationRequest(BaseModel):
    """Схема запроса для генерации дуа с выбором стиля."""
    style: VideoStyle = VideoStyle.NATURE
    custom_image_url: HttpUrl | None = None
    custom_audio_url: HttpUrl | None = None


class DuaResponse(BaseModel):
    """Схема для сгенерированного персонального дуа."""
    dua_text: str
    based_on_topics: list[str]
    shareable_text: str
    image_url: str | None = None
    video_url: str | None = None