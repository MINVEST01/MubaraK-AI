from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.user import UserCreate, UserUpdate
from src.core.security import get_password_hash
from src.db.models import User


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    """Получить пользователя по ID."""
    result = await db.execute(select(User).filter(User.id == user_id))
    return result.scalars().first()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Получить пользователя по email."""
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalars().first()


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
    """Получить список пользователей с пагинацией."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())


async def create_user(db: AsyncSession, user: UserCreate) -> User:
    """
    Создать нового пользователя.
    """
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email, hashed_password=hashed_password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def update_user(db: AsyncSession, *, db_user: User, user_in: UserUpdate) -> User:
    """Обновить данные пользователя."""
    user_data = user_in.model_dump(exclude_unset=True)

    if "password" in user_data and user_data["password"]:
        hashed_password = get_password_hash(user_data["password"])
        del user_data["password"]
        db_user.hashed_password = hashed_password

    for field, value in user_data.items():
        setattr(db_user, field, value)

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user