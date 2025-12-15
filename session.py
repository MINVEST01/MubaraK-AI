from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.core.config import settings

# Создаем асинхронный "движок" для SQLAlchemy на основе URL из настроек.
# pool_pre_ping=True проверяет соединение перед каждым запросом.
async_engine = create_async_engine(str(settings.DATABASE_URL), pool_pre_ping=True)

# Создаем фабрику асинхронных сессий.
# expire_on_commit=False предотвращает истечение срока действия объектов
# после коммита, что полезно в FastAPI.
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)