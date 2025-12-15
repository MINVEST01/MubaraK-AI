from typing import List
import secrets
from datetime import timedelta, datetime, timezone

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1 import schemas
from src.api.v1.schemas.user import UserBlockRequest
from src.api.v1.schemas.wallet import WalletLinkMessageResponse, WalletLinkRequest
from src.api.v1.schemas.token import Token
from src.crud import user as crud_user
from src.db.models import User as DBUser
from src.models.enums import UserRole
from src.api.deps import get_current_user, get_current_admin_user, RoleChecker
# Предполагается, что зависимость для получения сессии БД находится здесь
from src.db.session import get_db, redis_client
from src.core.security import verify_signature, create_access_token, verify_password
from src.core.config import settings

router = APIRouter()

logger = logging.getLogger(__name__)
# Создаем экземпляры зависимости для разных уровней доступа
allow_admin_only = RoleChecker([UserRole.ADMIN])
allow_moderator_and_admin = RoleChecker([UserRole.MODERATOR, UserRole.ADMIN])


@router.post("/login", response_model=Token)
async def login_for_access_token(
    db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Аутентифицирует пользователя и возвращает JWT-токен.
    """
    user = await crud_user.get_user_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Проверяем, не заблокирован ли пользователь
    if user.banned_until and user.banned_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Ваш аккаунт временно заблокирован до {user.banned_until.strftime('%Y-%m-%d %H:%M')} UTC."
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать нового пользователя.
    """
    db_user = await crud_user.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует.",
        )
    return await crud_user.create_user(db=db, user=user)


@router.get("/", response_model=List[schemas.User])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(allow_admin_only), # Используем новый экземпляр
):
    """
    Получить список пользователей (только для администраторов).
    """
    users = await crud_user.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/me", response_model=schemas.User)
async def read_user_me(current_user: DBUser = Depends(get_current_user)):
    """
    Получить информацию о текущем пользователе.
    """
    return current_user


@router.get("/{user_id}", response_model=schemas.User)
async def read_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить пользователя по ID.
    """
    db_user = await crud_user.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    return db_user


@router.put("/{user_id}", response_model=schemas.User)
async def update_user(
    user_id: int,
    user_in: schemas.UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """
    Обновить данные пользователя.
    Обычный пользователь может обновить только свой профиль.
    Администратор может обновить профиль любого пользователя.
    """
    db_user = await crud_user.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")

    # Проверяем права: пользователь должен быть либо владельцем профиля, либо администратором.
    if current_user.id != db_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав для выполнения этого действия.")

    updated_user = await crud_user.update_user(db=db, db_user=db_user, user_in=user_in)
    return updated_user


@router.post("/{user_id}/block", response_model=schemas.User)
async def block_user_temporarily(
    user_id: int,
    block_request: UserBlockRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: DBUser = Depends(allow_admin_only),
):
    """
    Временно заблокировать пользователя (только для администраторов).
    """
    user_to_block = await crud_user.get_user(db, user_id=user_id)
    if not user_to_block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")

    # Защита от блокировки других администраторов
    if user_to_block.role == UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нельзя заблокировать другого администратора.")

    # Рассчитываем дату окончания блокировки
    banned_until_date = datetime.now(timezone.utc) + block_request.duration

    # Обновляем пользователя через CRUD-функцию
    updated_user = await crud_user.update_user(db, db_user=user_to_block, user_in={"banned_until": banned_until_date})
    
    # Логируем действие администратора
    logger.info(
        "ADMIN ACTION: User '%s' (ID: %d) blocked user '%s' (ID: %d) for %s.",
        admin_user.email, admin_user.id,
        user_to_block.email, user_to_block.id,
        block_request.duration
    )
    return updated_user


@router.post("/{user_id}/unblock", response_model=schemas.User)
async def unblock_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: DBUser = Depends(allow_admin_only),
):
    """
    Разблокировать пользователя (только для администраторов).
    """
    user_to_unblock = await crud_user.get_user(db, user_id=user_id)
    if not user_to_unblock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")

    # Обновляем пользователя, устанавливая banned_until в None
    updated_user = await crud_user.update_user(db, db_user=user_to_unblock, user_in={"banned_until": None})

    # Логируем действие администратора
    logger.info(
        "ADMIN ACTION: User '%s' (ID: %d) unblocked user '%s' (ID: %d).",
        admin_user.email, admin_user.id,
        user_to_unblock.email, user_to_unblock.id
    )
    return updated_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    # Здесь должна быть логика удаления. Например:
    # db_user = await crud_user.get_user(db, user_id=user_id)
    # if not db_user:
    #     raise HTTPException(status_code=404, detail="Пользователь не найден.")
    # await db.delete(db_user)
    # await db.commit()
    return


@router.get("/me/link-wallet-message", response_model=WalletLinkMessageResponse)
async def get_link_wallet_message(current_user: DBUser = Depends(get_current_user)):
    """
    Шаг 1: Получить уникальное сообщение для подписи кошельком.
    """
    # Генерируем случайную строку (nonce) для предотвращения replay-атак
    nonce = secrets.token_hex(16)
    message = f"Я привязываю этот кошелек к моему аккаунту в MubarakAI. Nonce: {nonce}"

    # Сохраняем nonce в Redis с коротким временем жизни (например, 5 минут)
    # Ключ привязан к ID пользователя, чтобы избежать коллизий
    redis_client.set(f"link_wallet_nonce:{current_user.id}", nonce, ex=300)

    return WalletLinkMessageResponse(message=message)


@router.post("/me/link-wallet", response_model=schemas.User)
async def link_wallet(
    request_data: WalletLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """
    Шаг 2: Привязать кошелек к аккаунту после верификации подписи.
    """
    # 1. Проверяем, не занят ли этот кошелек другим пользователем
    existing_user = await crud_user.get_user_by_wallet(db, wallet_address=request_data.wallet_address)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот кошелек уже привязан к другому аккаунту."
        )

    # 2. Получаем nonce из Redis
    nonce_key = f"link_wallet_nonce:{current_user.id}"
    nonce = redis_client.get(nonce_key)
    if not nonce:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Время для подписи истекло. Пожалуйста, запросите новое сообщение."
        )

    # 3. Восстанавливаем исходное сообщение и проверяем подпись
    message = f"Я привязываю этот кошелек к моему аккаунту в MubarakAI. Nonce: {nonce.decode()}"
    is_valid = verify_signature(
        message=message,
        signature=request_data.signature,
        expected_address=request_data.wallet_address
    )

    # Удаляем nonce после использования, чтобы его нельзя было использовать повторно
    redis_client.delete(nonce_key)

    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Подпись недействительна.")

    # 4. Если все в порядке, обновляем профиль пользователя в PostgreSQL
    user_in = schemas.UserUpdate(wallet_address=request_data.wallet_address)
    updated_user = await crud_user.update_user(db=db, db_user=current_user, user_in=user_in)
    return updated_user