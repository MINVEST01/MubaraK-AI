from sqlalchemy.orm import declarative_base

# Создаем базовый класс для декларативных моделей SQLAlchemy.
# Все модели в приложении будут наследоваться от этого класса.
# Alembic использует metadata этого класса для обнаружения изменений в схеме.
Base = declarative_base()