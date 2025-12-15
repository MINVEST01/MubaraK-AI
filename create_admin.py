# c:\Users\Admin\OneDrive\Desktop\MubaraK-AI\create_admin.py
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем необходимые компоненты из вашего проекта
from src.db.session import AsyncSessionLocal
from src.crud import user as crud_user
from src.api.v1 import schemas
from src.models.enums import UserRole
from src.core.security import get_password_hash

async def create_or_update_admin_user():
    """
    Создает или обновляет пользователя с указанным email и паролем,
    устанавливая ему роль администратора.
    """
    admin_email = "info.minvestrk@bk.ru"
    admin_password = "пароль от почты" # Используйте предоставленный пароль

    async with AsyncSessionLocal() as db:
        # Пытаемся найти пользователя по email
        existing_user = await crud_user.get_user_by_email(db, email=admin_email)

        if existing_user:
            print(f"Пользователь с email '{admin_email}' уже существует. Обновляем его данные...")
            # Обновляем пароль и убеждаемся, что роль установлена как ADMIN
            user_update_data = schemas.UserUpdate(
                password=admin_password,
                role=UserRole.ADMIN
            )
            updated_user = await crud_user.update_user(
                db, db_user=existing_user, user_in=user_update_data
            )
            print(f"Пользователь '{updated_user.email}' успешно обновлен. Роль: {updated_user.role}")
        else:
            print(f"Пользователь с email '{admin_email}' не найден. Создаем нового администратора...")
            # Создаем нового пользователя с ролью ADMIN
            user_create_data = schemas.UserCreate(
                email=admin_email,
                password=admin_password,
                role=UserRole.ADMIN
            )
            new_admin_user = await crud_user.create_user(db, user_create_data)
            print(f"Новый администратор '{new_admin_user.email}' успешно создан. Роль: {new_admin_user.role}")

if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(create_or_update_admin_user())
