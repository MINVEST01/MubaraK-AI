import json
from functools import wraps
from typing import Callable, Coroutine, Any


def _generate_cache_key(func: Callable, *args, **kwargs) -> str:
    """Генерирует уникальный ключ для кэша на основе имени функции и аргументов."""
    key_parts = [func.__name__]
    # Пропускаем 'self' и 'db_session' из ключа
    key_parts.extend(map(str, (arg for arg in args if not (hasattr(arg, '__class__') and arg.__class__.__name__ == 'AsyncSession'))))
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()) if k != 'db_session')
    cache_key = f"cache:{':'.join(key_parts)}"
    return cache_key


def redis_cache(expiration: int = 3600):
    """
    Асинхронный декоратор для кэширования результатов функций в Redis.

    :param expiration: Время жизни кэша в секундах.
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Ожидается, что у объекта 'self' есть атрибут 'redis'
            if not hasattr(self, 'redis') or self.redis is None:
                # Если Redis не настроен, просто вызываем функцию
                return await func(self, *args, **kwargs)

            cache_key = _generate_cache_key(func, *args, **kwargs)

            # 1. Попытка получить данные из кэша
            cached_result = await self.redis.get(cache_key)
            if cached_result:
                # Если данные найдены, десериализуем и возвращаем их
                return json.loads(cached_result)

            # 2. Если в кэше данных нет (cache miss)
            # Выполняем оригинальную функцию для получения данных из БД
            result = await func(self, *args, **kwargs)

            # 3. Сериализуем результат в JSON и сохраняем в Redis с указанным временем жизни
            try:
                json_result = json.dumps(result)
                await self.redis.setex(cache_key, expiration, json_result)
            except (TypeError, OverflowError) as e:
                # Не удалось сериализовать, просто пропускаем кэширование
                self.logger.warning(f"Не удалось кэшировать результат для ключа {cache_key}: {e}")

            return result
        return wrapper
    return decorator