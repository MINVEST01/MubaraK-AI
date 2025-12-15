import hashlib
import json
from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from src.api.schemas.ai_analysis import AnalysisRequest, AnalysisResponse
from src.core.spirit_analyzer import SpiritAnalyzer
from src.db.redis_client import get_redis_client
from src.api.deps import get_current_user
from src.db import models

router = APIRouter()
CACHE_EXPIRATION_SECONDS = 3600  # 1 час
# Создаем зависимость для SpiritAnalyzer, чтобы не инициализировать его при каждом запросе.
# FastAPI кэширует результат функции Depends без параметров в рамках одного запроса.
def get_spirit_analyzer() -> SpiritAnalyzer:
    return SpiritAnalyzer()


@router.post("/analyze-text", response_model=AnalysisResponse)
async def analyze_user_text(
    request_data: AnalysisRequest,
    analyzer: SpiritAnalyzer = Depends(get_spirit_analyzer),
    redis_client: Redis = Depends(get_redis_client),
    current_user: models.User = Depends(get_current_user)
):
    """
    Анализирует предоставленный текст для определения его эмоционального
    и тематического окраса в исламском контексте.
    Результаты кэшируются на 1 час.
    """
    # 1. Создаем уникальный и безопасный ключ для кэша на основе хэша текста
    text_hash = hashlib.sha256(f"{current_user.id}:{request_data.text}".encode()).hexdigest()
    cache_key = f"analysis:{text_hash}"

    # 2. Пытаемся получить результат из кэша Redis
    cached_result = await redis_client.get(cache_key)
    if cached_result:
        print(f"CACHE HIT for key: {cache_key}")
        return {"results": json.loads(cached_result)}

    print(f"CACHE MISS for key: {cache_key}")
    # 3. Если в кэше ничего нет, выполняем анализ
    analysis_results = analyzer.analyze_topics(request_data.text)

    # 4. Сохраняем результат в кэш Redis с временем жизни
    await redis_client.set(
        cache_key, json.dumps(analysis_results), ex=CACHE_EXPIRATION_SECONDS
    )

    return {"results": analysis_results}