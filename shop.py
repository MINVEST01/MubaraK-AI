from pydantic import BaseModel
from enum import Enum


class ShopItemType(str, Enum):
    """Типы товаров в магазине."""
    DONATION = "donation"
    DIGITAL_GOOD = "digital_good"


class ShopItem(BaseModel):
    """Схема для одного товара в магазине."""
    id: str
    name: str
    description: str
    cost: int
    type: ShopItemType


class PurchaseRequest(BaseModel):
    """Схема запроса на покупку товара."""
    item_id: str

class PurchaseResponse(BaseModel):
    """Схема ответа после успешной покупки."""
    message: str
    remaining_points: int