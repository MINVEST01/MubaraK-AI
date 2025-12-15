import pytest
from fastapi.testclient import TestClient
from typing import Generator
from typing import List
import fakeredis.aioredis
from datetime import datetime, timezone, timedelta

from src.main import create_app
from src.core.security import get_password_hash
from src.crud import user as crud_user
from src.db.session import get_db
from src.api.deps import get_current_user
from src.api.v1 import schemas
from src.db import models
from src.models.enums import UserRole
from src.db.session import AsyncSessionLocal, async_engine
from src.api.deps import get_current_user
from src.db import models
from src.models.enums import UserRole


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """
    Фикстура для создания тестового клиента FastAPI.
    """
    app = create_app()
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="session")
def db() -> Generator[AsyncSession, None, None]:
    """
    Фикстура для получения сессии базы данных для тестов.
    """
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture(scope="function")
async def normal_user_in_db(db: AsyncSession):
    """
    Фикстура для создания и очистки обычного пользователя (role=USER).
    """
    user = await crud_user.create_user(db, schemas.UserCreate(email="testuser@example.com", password="password"))
    yield user
    await crud_user.delete_user(db, user.id)

@pytest.fixture(scope="function")
async def another_user_in_db(db: AsyncSession):
    user = await crud_user.create_user(db, schemas.UserCreate(email="anotheruser@example.com", password="password"))
    yield user
    await crud_user.delete_user(db, user.id)

@pytest.fixture(scope="function")
async def admin_user_in_db(db: AsyncSession):
    """
    Фикстура для создания и очистки пользователя-администратора (role=ADMIN).
    """
    user = await crud_user.create_user(db, schemas.UserCreate(email="admin@example.com", password="password", role=UserRole.ADMIN))
    yield user
    await crud_user.delete_user(db, user.id)

@pytest.fixture(scope="function")
async def another_admin_in_db(db: AsyncSession):
    user = await crud_user.create_user(db, schemas.UserCreate(email="admin2@example.com", password="password", role=UserRole.ADMIN))
    yield user
    await crud_user.delete_user(db, user.id)

@pytest.fixture(scope="function")
async def blocked_user_in_db(db: AsyncSession):
    """
    Фикстура для создания и очистки заблокированного пользователя.
    """
    user = await crud_user.create_user(db, schemas.UserCreate(email="blocked@example.com", password="password"))
    banned_until_date = datetime.now(timezone.utc) + timedelta(days=1)
    blocked_user = await crud_user.update_user(db, db_user=user, user_in={"banned_until": banned_until_date})
    yield blocked_user
    await crud_user.delete_user(db, blocked_user.id)

@pytest.fixture
def client_as_normal_user(client: TestClient, normal_user_in_db: models.User):
    """
    Фикстура, которая предоставляет тестовый клиент,
    аутентифицированный как обычный пользователь.
    """
    app.dependency_overrides[get_current_user] = lambda: normal_user_in_db
    yield client
    # Очистка после выполнения теста
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client_as_admin(client: TestClient, admin_user_in_db: models.User):
    """
    Фикстура, которая предоставляет тестовый клиент,
    аутентифицированный как администратор.
    """
    app.dependency_overrides[get_current_user] = lambda: admin_user_in_db
    yield client
    # Очистка после выполнения теста
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture(scope="function")
def override_get_redis_client():
    """
    Подменяет зависимость Redis на in-memory имитацию (fakeredis).
    `scope="function"` гарантирует, что для каждого теста будет чистый кэш.
    """
    # Создаем асинхронный мок-клиент
    fake_redis_client = fakeredis.aioredis.FakeRedis()
    app.dependency_overrides[get_redis_client] = lambda: fake_redis_client
    yield
    # Очищаем мок после теста
    app.dependency_overrides.pop(get_redis_client, None)


# --- Отключаем зависимость get_current_user для этих тестов ---
from src.api.deps import get_current_user
from src.main import app
app.dependency_overrides[get_current_user] = lambda: None