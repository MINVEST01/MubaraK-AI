from fastapi.testclient import TestClient
from typing import List, Dict
import fakeredis.aioredis
from unittest.mock import MagicMock
from src.api.v1.endpoints.ai_analysis import get_spirit_analyzer
import pytest

from src.main import app
from src.core.spirit_analyzer import SpiritAnalyzer
# --- Создание "мока" (имитации) для SpiritAnalyzer ---

class MockSpiritAnalyzer:
    """
    Имитация анализатора, которая возвращает предопределенный результат
    без вызова реальной ML-модели.
    """
    def analyze_topics(self, text: str) -> List[Dict[str, float]]:
        # Убедимся, что метод был вызван с правильным текстом
        assert text == "Это достаточно длинный текст для успешного прохождения валидации."
        
        # Возвращаем заранее подготовленный ответ
        return [
            {"label": "PATIENCE", "score": 0.9},
            {"label": "HOPE", "score": 0.75},
        ]

def override_get_spirit_analyzer():
    """
    Эта функция будет подменять оригинальную зависимость `get_spirit_analyzer`.
    """
    return MockSpiritAnalyzer()

def override_get_current_user():
    """
    Подменяет зависимость get_current_user, чтобы возвращать
    тестового пользователя (модель User) без реальной проверки токена.
    """
    # Создаем объект, который имитирует модель SQLAlchemy User
    return models.User(id=123, email="test@example.com", role=UserRole.USER, is_active=True)

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


# --- Применение подмен зависимостей ---
# FastAPI будет использовать эти функции вместо реальных зависимостей во время тестов.
app.dependency_overrides[get_spirit_analyzer] = override_get_spirit_analyzer
app.dependency_overrides[get_current_user] = override_get_current_user

# --- Тесты для эндпоинта /api/v1/ai/analyze-text ---

async def test_analyze_text_caching(client: TestClient, override_get_redis_client):
    """
    Тест успешного анализа текста с валидными данными.
    """
    # Arrange: готовим данные для запроса
    request_payload = {"text": "Это достаточно длинный текст для успешного прохождения валидации."}
    auth_headers = {"Authorization": "Bearer fake-token"}
    
    # --- 1. Первый вызов (Cache Miss) ---
    # Act: делаем первый запрос к API
    response = client.post(
        "/api/v1/ai/analyze-text",
        json=request_payload,
        headers=auth_headers
    )
    
    # Assert: проверяем, что все прошло успешно
    assert response_miss.status_code == 200
    
    # --- 2. Второй вызов (Cache Hit) ---
    # Act: делаем второй, точно такой же запрос
    response_hit = client.post(
        "/api/v1/ai/analyze-text",
        json=request_payload,
        headers=auth_headers
    )
    
    # Assert: проверяем результат
    assert response_hit.status_code == 200
    response_data = response_hit.json()
    
    # Проверяем, что данные из первого и второго запроса идентичны
    assert response_miss.json() == response_hit.json()
    assert response_data == {
        "results": [
            {"label": "PATIENCE", "score": 0.9},
            {"label": "HOPE", "score": 0.75},
        ]
    }

async def test_analyzer_is_not_called_on_cache_hit(client: TestClient, override_get_redis_client):
    """
    Тест, который проверяет, что SpiritAnalyzer.analyze_topics
    не вызывается при наличии результата в кэше.
    """
    # 1. Arrange: Настраиваем моки
    # Создаем MagicMock, который будет отслеживать вызовы
    mock_analyzer = MagicMock(spec=SpiritAnalyzer)
    mock_analyzer.analyze_topics.return_value = [{"label": "TEST", "score": 0.99}]

    # Подменяем зависимость анализатора на наш MagicMock
    app.dependency_overrides[get_spirit_analyzer] = lambda: mock_analyzer

    request_payload = {"text": "Это достаточно длинный текст для успешного прохождения валидации."}
    auth_headers = {"Authorization": "Bearer fake-token"}

    # 2. Act: Первый вызов (Cache Miss)
    response_miss = client.post(
        "/api/v1/ai/analyze-text",
        json=request_payload,
        headers=auth_headers
    )

    # 3. Assert: Проверяем, что анализатор был вызван один раз
    assert response_miss.status_code == 200
    mock_analyzer.analyze_topics.assert_called_once_with(request_payload["text"])

    # 4. Act: Второй вызов (Cache Hit)
    response_hit = client.post(
        "/api/v1/ai/analyze-text",
        json=request_payload,
        headers=auth_headers
    )

    # 5. Assert: Проверяем, что анализатор НЕ был вызван снова.
    # Общее количество вызовов должно остаться равным 1.
    assert response_hit.status_code == 200
    mock_analyzer.analyze_topics.assert_called_once() # Проверяем, что вызов был все еще один

    # Очищаем подмену после теста
    app.dependency_overrides.pop(get_spirit_analyzer, None)

def test_analyze_text_validation_error_too_short(client: TestClient, override_get_redis_client):
    """
    Тест ошибки валидации, если текст слишком короткий (min_length=10).
    """
    auth_headers = {"Authorization": "Bearer fake-token"}
    response = client.post(
        "/api/v1/ai/analyze-text",
        json={"text": "коротко"},
        headers=auth_headers
    )
    assert response.status_code == 422 # Unprocessable Entity

def test_analyze_text_validation_error_missing_field(client: TestClient, override_get_redis_client):
    """
    Тест ошибки валидации, если поле 'text' отсутствует.
    """
    auth_headers = {"Authorization": "Bearer fake-token"}
    response = client.post(
        "/api/v1/ai/analyze-text",
        json={"wrong_field": "some text"},
        headers=auth_headers
    )
    assert response.status_code == 422