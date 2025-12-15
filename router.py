from fastapi import APIRouter

# Импортируем модули с роутерами из папки endpoints
from src.api.v1.endpoints import users
from src.api.v1.endpoints import blockchain
from src.api.v1.endpoints import ai_analysis # 1. Импортируем роутер анализа


api_router = APIRouter()

# Подключаем роутеры из модулей, указывая префикс и теги для группировки в документации
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(blockchain.router, prefix="/blockchain", tags=["Blockchain"])
api_router.include_router(ai_analysis.router, prefix="/ai", tags=["AI Analysis"]) # 2. Подключаем роутер анализа