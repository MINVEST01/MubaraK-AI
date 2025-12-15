from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserRegistration(BaseModel):
    email: EmailStr
    phone: str
    full_name: str
    birth_year: int
    gender: str
    location: Dict[str, Any]
    profession: Optional[str] = None
    language: Optional[str] = Field("ru", max_length=2)
    career_level: Optional['JobLevel'] = None


class GenericRequest(BaseModel):
    module: str
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeSessionCreate(BaseModel):
    topic: str
    time: str


class InvestmentRequest(BaseModel):
    waqf_id: str
    amount: float = Field(..., gt=0)


class FitnessGoalCreate(BaseModel):
    goal_type: str
    target: str
    deadline: Optional[str] = None

class WaqfCreate(BaseModel):
    name: str
    category: str
    description: str
    yield_pa: float = Field(0.0, ge=0, description="Ожидаемая годовая доходность, например, 0.08 для 8%")


class JobPostCreate(BaseModel):
    title: str
    description: str
    company_name: Optional[str] = None
    location: str
    is_remote: bool = False
    level: Optional['JobLevel'] = None


class JobLevel(str, Enum):
    """Допустимые уровни для вакансий."""
    INTERN = "intern"
    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"
    LEAD = "lead"


class ApplicationStatus(str, Enum):
    """Допустимые статусы для отклика на вакансию."""
    VIEWED = "viewed"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


class JobApplicationUpdate(BaseModel):
    status: ApplicationStatus

# Обновляем ссылку после определения Enum
JobPostCreate.model_rebuild()
# Добавляем для UserRegistration
UserRegistration.model_rebuild()

class NodeRegistration(BaseModel):
    nodes: List[str] = Field(..., description="Список адресов узлов для регистрации, например, ['http://192.168.0.5:5001']")
# Добавляем для UserRegistration
UserRegistration.model_rebuild()