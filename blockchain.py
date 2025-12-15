from pydantic import BaseModel, Field


class TransactionSchema(BaseModel):
    """
    Схема для валидации данных новой транзакции "Барака Поинтов".
    """
    sender: str = Field(
        ...,
        description="Адрес (ID) отправителя. '0' для системных транзакций (например, вознаграждение за майнинг)."
    )
    recipient: str = Field(..., description="Адрес (ID) получателя.")
    amount: int = Field(..., gt=0, description="Сумма перевода. Должна быть положительным числом.")

    class Config:
        json_schema_extra = {"example": {"sender": "user_uuid_1", "recipient": "waqf_uuid_2", "amount": 100}}