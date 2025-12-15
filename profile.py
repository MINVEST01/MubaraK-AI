from pydantic import BaseModel


class InterestDynamics(BaseModel):
    """Схема для отображения динамики интереса к теме."""
    month: str  # Например, "2025-12"
    count: int
    

class TopicPreference(BaseModel):
    """Схема для представления одной темы в профиле."""
    topic: str
    count: int
    percentage: float


class SpiritualProfile(BaseModel):
    """
    Схема для представления духовного профиля пользователя.
    """
    dominant_topic: str | None
    summary: str
    top_topics: list[TopicPreference]
    interest_dynamics: list[InterestDynamics] | None = None