from fastapi import Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# 1. Создание экземпляра Rate Limiter
# Используем IP-адрес пользователя как ключ для отслеживания запросов.
limiter = Limiter(key_func=lambda request: request.client.host)


# 2. Middleware для добавления заголовков безопасности
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        # Защита от кликджекинга. Запрещает встраивание страницы в <iframe> на других сайтах.
        response.headers["X-Frame-Options"] = "DENY"
        # Защита от XSS. Указывает браузеру не угадывать тип контента.
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Указывает браузеру использовать только HTTPS для всех будущих запросов к этому домену.
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        # Базовая политика безопасности контента. Разрешает загрузку ресурсов только с того же источника.
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response


# 3. Функция для инициализации всех middleware в приложении
def setup_middlewares(app):
    # Добавляем обработчик для ошибок превышения лимита
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Добавляем middleware для заголовков безопасности
    app.add_middleware(SecurityHeadersMiddleware)