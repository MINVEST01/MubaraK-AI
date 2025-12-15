from sqlalchemy import Integer, String, Boolean, JSON, DateTime, func, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship, MappedAsDataclass

from src.db.base import Base


class User(Base):
    """
    Пример модели пользователя в базе данных.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Новое поле для хранения предпочтений пользователя в Ilham-AI
    # Ключ - основное слово темы, значение - количество обращений.
    ilham_preferences: Mapped[dict] = mapped_column(JSON, server_default='{}', nullable=False)

    # Настройка для включения/отключения контекстных подсказок от Ilham-AI
    settings_enable_ilham_contextual: Mapped[bool] = mapped_column(Boolean, server_default='true', nullable=False)

    # Токен для отправки push-уведомлений
    push_notification_token: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    # Настройки для "Аята дня"
    settings_daily_ayat_time: Mapped[str | None] = mapped_column(String, server_default='08:00', nullable=False) # Время в формате HH:MM
    settings_timezone: Mapped[str | None] = mapped_column(String, server_default='UTC', nullable=False) # Часовой пояс, например, 'Europe/Moscow'

    # Настройка типа ежедневного контента: 'ayat', 'story', 'alternate'
    settings_daily_content_type: Mapped[str] = mapped_column(String, server_default='ayat', nullable=False)

    # Очки за благие дела и использование платформы
    baraka_points: Mapped[int] = mapped_column(Integer, server_default='0', nullable=False)

    # Связи с другими моделями
    purchases: Mapped[list["Purchase"]] = relationship(back_populates="user")
    prayer_logs: Mapped[list["PrayerLog"]] = relationship(back_populates="user")
    created_waqfs: Mapped[list["Waqf"]] = relationship(back_populates="creator")
    donations: Mapped[list["WaqfDonation"]] = relationship(back_populates="donor")

    # Здесь можно добавить связи (relationships) с другими моделями.


class Purchase(Base):
    """Модель для хранения покупок в Магазине Бараката."""
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_id: Mapped[str] = mapped_column(String, nullable=False)
    item_name: Mapped[str] = mapped_column(String, nullable=False)
    cost_in_points: Mapped[int] = mapped_column(Integer, nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="purchases")


class PrayerLog(Base):
    """Модель для хранения записей о выполненных намазах."""
    __tablename__ = "prayer_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    prayer_name: Mapped[str] = mapped_column(String, nullable=False) # Например, "fajr", "dhuhr"
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="prayer_logs")


class Waqf(Base):
    """Модель для цифрового вакфа (благотворительного фонда)."""
    __tablename__ = "waqfs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, index=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    total_value: Mapped[float] = mapped_column(Float, server_default='0.0', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    creator: Mapped["User"] = relationship(back_populates="created_waqfs")
    donations: Mapped[list["WaqfDonation"]] = relationship(back_populates="waqf")