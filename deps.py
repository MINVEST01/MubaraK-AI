from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db import models
from src.crud import user as crud_user
from src.db.session import get_db
from src.api.v1.schemas.token import TokenPayload

# Эта схема определяет, какие данные мы ожидаем найти в полезной нагрузке (payload) токена.
# (Перенесено в schemas/token.py)


# Создаем схему аутентификации.
# tokenUrl указывает на эндпоинт, где клиент может получить токен (его нужно будет создать отдельно).
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/users/login"
)


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> models.User:
    """
    Декодирует JWT-токен, валидирует его и возвращает
    полную модель пользователя из базы данных.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Декодируем токен с помощью секретного ключа и алгоритма из настроек
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # Валидируем полезную нагрузку с помощью Pydantic-схемы
        token_data = TokenPayload(**payload)
        if token_data.sub is None:
            raise credentials_exception
    # Если токен невалиден (неправильная подпись, истек срок действия и т.д.)
    except (JWTError, ValidationError):
        raise credentials_exception

    # Ищем пользователя в БД по ID из токена
    user = await crud_user.get_user(db, user_id=int(token_data.sub))
    if user is None:
        raise credentials_exception
    return user