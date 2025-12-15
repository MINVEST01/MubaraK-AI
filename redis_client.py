import redis.asyncio as aioredis
from src.core.config import settings

# Создаем пул соединений Redis при старте приложения.
# Это более эффективно, чем создание нового соединения при каждом запросе.
redis_pool = aioredis.from_url(
    str(settings.REDIS_URL),
    encoding="utf-8",
    decode_responses=True # Автоматически декодировать ответы из bytes в str
)

async def get_redis_client() -> aioredis.Redis:
    """
    Зависимость FastAPI для получения клиента Redis из пула соединений.
    """
    yield redis_pool