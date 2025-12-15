import pytest
from fastapi.testclient import TestClient
from fastapi import status
from datetime import datetime, timezone, timedelta
from typing import Generator



def test_login_success(client: TestClient, test_user):
    """
    Тест успешного входа пользователя и получения JWT-токена.
    """
    login_data = {"username": test_user.email, "password": "test_password"}
    response = client.post("/api/v1/users/login", data=login_data)
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_incorrect_username(client: TestClient, test_user):
    """
    Тест входа с неверным email.
    """
    login_data = {"username": "wrong@example.com", "password": "test_password"}
    response = client.post("/api/v1/users/login", data=login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Неверный email или пароль" in response.json()["detail"]


def test_login_incorrect_password(client: TestClient, test_user):
    """
    Тест входа с неверным паролем.
    """
    login_data = {"username": test_user.email, "password": "wrong_password"}
    response = client.post("/api/v1/users/login", data=login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Неверный email или пароль" in response.json()["detail"]


def test_login_missing_fields(client: TestClient, test_user):
    """
    Тест входа с отсутствующими полями (username или password).
    """
    response = client.post("/api/v1/users/login", data={"username": test_user.email})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    response = client.post("/api/v1/users/login", data={"password": "test_password"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_login_banned_user(client: TestClient, blocked_user_in_db):
    """
    Тест: Заблокированный пользователь не может войти в систему.
    """
    login_data = {"username": blocked_user_in_db.email, "password": "password"}
    response = client.post("/api/v1/users/login", data=login_data)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    response_data = response.json()
    assert "Ваш аккаунт временно заблокирован" in response_data["detail"]
    assert "access_token" not in response_data

async def test_login_after_ban_expires(client: TestClient, db: AsyncSession):
    """
    Тест: Пользователь может войти в систему после истечения срока блокировки.
    """
    # 1. Создаем пользователя и блокируем его на 5 минут
    user = await crud_user.create_user(db, schemas.UserCreate(email="tempblocked@example.com", password="password"))
    start_time = datetime.now(timezone.utc)
    banned_until = start_time + timedelta(minutes=5)
    await crud_user.update_user(db, db_user=user, user_in={"banned_until": banned_until})

    login_data = {"username": user.email, "password": "password"}

    # 2. Перемещаемся на 4 минуты вперед (пользователь все еще заблокирован)
    with freeze_time(start_time + timedelta(minutes=4)):
        response_banned = client.post("/api/v1/users/login", data=login_data)
        assert response_banned.status_code == status.HTTP_403_FORBIDDEN

    # 3. Перемещаемся на 6 минут вперед (срок блокировки истек)
    with freeze_time(start_time + timedelta(minutes=6)):
        response_unbanned = client.post("/api/v1/users/login", data=login_data)
        assert response_unbanned.status_code == status.HTTP_200_OK
        assert "access_token" in response_unbanned.json()

    # Очистка
    await crud_user.delete_user(db, user.id)


# --- Тесты для блокировки пользователя ---

def test_admin_blocks_user_success(client_as_admin, normal_user_in_db):
    """
    Тест: Администратор успешно блокирует обычного пользователя.
    """
    response = client.post(
        f"/api/v1/users/{normal_user_in_db.id}/block",
        json={"duration": "PT1H"} # Блокировка на 1 час
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert response_data["id"] == normal_user_in_db.id
    # Проверяем, что дата блокировки установлена и находится в будущем
    assert datetime.fromisoformat(response_data["banned_until"]) > datetime.now(timezone.utc)


def test_user_cannot_block_another_user(client_as_normal_user, another_user_in_db):
    """
    Тест: Обычный пользователь не может заблокировать другого пользователя.
    """
    response = client.post(
        f"/api/v1/users/{another_user_in_db.id}/block",
        json={"duration": "PT1H"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_cannot_block_another_admin(client_as_admin, another_admin_in_db):
    """
    Тест: Администратор не может заблокировать другого администратора.
    """
    response = client.post(
        f"/api/v1/users/{another_admin_in_db.id}/block",
        json={"duration": "PT1H"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Нельзя заблокировать другого администратора" in response.json()["detail"]


# --- Тесты для разблокировки пользователя ---

def test_admin_unblocks_user_success(client_as_admin, blocked_user_in_db):
    """
    Тест: Администратор успешно разблокирует пользователя.
    """
    # Убедимся, что пользователь действительно заблокирован
    assert blocked_user_in_db.banned_until is not None

    response = client.post(f"/api/v1/users/{blocked_user_in_db.id}/unblock")

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert response_data["id"] == blocked_user_in_db.id
    # Проверяем, что дата блокировки теперь None
    assert response_data["banned_until"] is None


def test_user_cannot_unblock_user(client_as_normal_user, blocked_user_in_db):
    """
    Тест: Обычный пользователь не может разблокировать другого пользователя.
    """
    response = client.post(f"/api/v1/users/{blocked_user_in_db.id}/unblock")

    assert response.status_code == status.HTTP_403_FORBIDDEN


# --- Фикстуры для аутентификации ---

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


# --- Фикстура для создания тестового пользователя в БД ---
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

# Переименовываем старую фикстуру для обратной совместимости
@pytest.fixture
async def test_user(normal_user_in_db):
    return normal_user_in_db


# --- Переопределение зависимости для получения сессии БД ---
@pytest.fixture(scope="session")
def db() -> Generator[AsyncSession, None, None]:
    """
    Фикстура для получения сессии базы данных для тестов.
    """
    async with get_db() as session:
        yield session


# --- Отключаем зависимость get_current_user для этих тестов ---
app.dependency_overrides[get_current_user] = lambda: None