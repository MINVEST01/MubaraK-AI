import asyncio
import hashlib
import logging
import random
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4
from typing import Any, Dict, List, Optional, Tuple

import uvicorn
import redis.asyncio as redis
from api.server import create_app
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from core.db_models import Base, MubarakUserDB
from core.analytics import AnalyticsEngine
from core.blockchain import BlockchainLedger
from core.notifications import NotificationService
from core.orchestrator import CrossModuleOrchestrator
from core.recommendations import RecommendationEngine
from models import ActivityType, ModuleType, MubarakUser, UserRole
from modules.ar_rihla import ArRihlaModule
from modules.baitul_hikma import BaitulHikmaModule
from modules.career_umma import CareerUmmaModule
from modules.fard_ai import FardAIModule
from modules.nutrition_halal import NutritionHalalModule
from modules.salam_health import SalamHealthModule
from modules.ummah_waqf import UmmahWaqfModule

logger = logging.getLogger(__name__)

# ========== MUBARAKAI ОСНОВНОЙ КЛАСС ==========

class MubarakAI:
    """Основной класс универсального приложения MubarakAI"""
    
    def __init__(self):
        # Инициализация модулей
        self.modules = {
            ModuleType.FARD_AI: FardAIModule(),
            ModuleType.BAITUL_HIKMA: BaitulHikmaModule(),
            ModuleType.AR_RIHLA: ArRihlaModule(),
            ModuleType.UMMAH_WAQF: UmmahWaqfModule(),
            ModuleType.SALAM_HEALTH: SalamHealthModule(),
            ModuleType.NUTRITION_HALAL: NutritionHalalModule(),
            ModuleType.CAREER_UMMA: CareerUmmaModule(),
        }
        self.orchestrator = CrossModuleOrchestrator()
        for module in self.modules.values(): # pragma: no cover
            self.orchestrator.register_module(module)
        
        # --- Инициализация базы данных ---
        # Используем SQLite для простоты, в production лучше использовать PostgreSQL
        # URL для подключения берется из переменной окружения.
        # Для SQLite мы строим абсолютный путь внутри контейнера.
        default_db_path = os.path.join(os.getcwd(), "data", "mubarakai.db")
        database_url = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{default_db_path}")
        self.engine = create_async_engine(database_url)
        self.Session = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)
        
        # --- Устаревшие хранилища в памяти (можно удалить или оставить для кэша некритичных данных) ---
        self.sessions: Dict[str, Dict] = {}
        self.analytics_engine = AnalyticsEngine()
        self.recommendation_engine = RecommendationEngine()
        self.notification_service = NotificationService()
        self.main_ledger = BlockchainLedger()
        # Порог для создания нового блока в блокчейне
        self.BLOCK_CREATION_THRESHOLD = 5
        # Уникальный идентификатор этого узла (сервера)
        self.node_identifier = str(uuid4()).replace('-', '')
        # Ссылка на фоновую задачу для корректного завершения
        self.block_creation_task = None
        # Множество для хранения адресов соседних узлов
        self.nodes = set()

        # --- Инициализация клиента Redis ---
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis = redis.from_url(redis_url, decode_responses=True)
        for module in self.modules.values():
            module.set_redis_client(self.redis)
            module.set_notification_service(self.notification_service)
            module.set_ledger(self.main_ledger)

    async def create_db_tables(self):
        """Создает таблицы в БД, если их нет."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # После создания таблиц, можно заполнить их начальными данными
        async with self.get_db_session() as db_session:
            ummah_waqf_module = self.modules.get(ModuleType.UMMAH_WAQF)
            if ummah_waqf_module and hasattr(ummah_waqf_module, '_seed_mock_data'):
                await ummah_waqf_module._seed_mock_data(db_session)
            # Сюда же можно добавить seed'еры для других модулей

    async def _periodic_block_creation_task(self):
        """Фоновая задача, которая создает новый блок каждые 10 минут, если есть транзакции."""
        while True:
            await asyncio.sleep(600)  # 10 минут
            if self.main_ledger.pending_transactions:
                self.logger.info("Периодическая задача: создание нового блока для ожидающих транзакций.")
                self.main_ledger.create_block(proof=random.randint(1, 100000), miner=self.node_identifier) # pragma: no cover
            else:
                self.logger.info("Периодическая задача: нет ожидающих транзакций, блок не создан.") # pragma: no cover


    @asynccontextmanager
    async def get_db_session(self):
        """Контекстный менеджер для управления сессиями БД."""
        session = self.Session()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def register_user(self, user_data: Dict) -> Tuple[bool, str, Dict]:
        """Регистрация нового пользователя"""
        try:
            user_id = hashlib.sha256(
                f"{user_data['email']}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
            user = MubarakUser(
                user_id=user_id,
                wallet_address=user_data.get('wallet_address', ''),
                email=user_data['email'],
                phone=user_data['phone'],
                full_name=user_data['full_name'],
                birth_year=user_data['birth_year'],
                gender=user_data['gender'],
                location=user_data['location'],
                roles=self._detect_initial_roles(user_data)
            )

            # Генерация и сохранение API-ключа
            api_key = hashlib.sha256(f"{user_id}{datetime.now().isoformat()}".encode()).hexdigest()

            async with self.get_db_session() as db_session:
                # Создаем пользователя в БД
                new_user_db = MubarakUserDB(
                    user_id=user_id,
                    full_name=user.full_name,
                    email=user.email,
                    api_key=api_key,
                    career_level=user_data.get("career_level")
                )
                db_session.add(new_user_db)
                await db_session.commit()

            module_initializations = {}
            for module_type, module in self.modules.items():
                # TODO: Передать dataclass MubarakUser, а не объект БД
                if hasattr(module, 'initialize'):
                    module_initializations[module_type.value] = await module.initialize(user)

            self.sessions[user_id] = {
                "created_at": datetime.now().isoformat(),
                "active_modules": list(self.modules.keys()),
                "module_states": module_initializations
            }
            welcome_package = await self._generate_welcome_package(user)
            
            return True, user_id, {
                "user": asdict(user),
                "api_key": api_key,
                "module_initializations": module_initializations,
                "welcome_package": welcome_package,
                "next_steps": [
                    "complete_profile",
                    "setup_preferences", 
                    "explore_modules",
                    "join_community"
                ]
            }
        except Exception as e:
            logger.exception(f"Ошибка регистрации пользователя: {user_data.get('email')}")
            return False, str(e), {}

    def register_nodes(self, nodes: List[str]) -> Dict[str, Any]:
        """
        Регистрирует новые узлы в сети.

        :param nodes: Список адресов узлов, например, ['http://192.168.0.5:5001']
        """
        for node_url in nodes:
            try:
                parsed_url = urlparse(node_url)
                if parsed_url.netloc:
                    self.nodes.add(parsed_url.netloc)
                elif parsed_url.path: # Для адресов без схемы, например, '192.168.0.5:5001'
                    self.nodes.add(parsed_url.path)
                else:
                    raise ValueError(f"Некорректный URL узла: {node_url}")
            except ValueError as e:
                logger.warning(f"Ошибка при регистрации узла: {e}")
        
        return {"message": "Новые узлы успешно добавлены", "total_nodes": list(self.nodes)}
    
    async def process_request(self, user_id: str, request: Dict) -> Dict[str, Any]:
        """Обработка запроса пользователя"""
        request_id = hashlib.sha256(f"{user_id}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
        logger.info(f"[RequestID: {request_id}] Получен запрос от пользователя {user_id}: {request}")
        
        request_type = request.get("type")
        module_name = request.get("module")
        module_type = ModuleType(module_name) if module_name else ModuleType.FARD_AI
        
        if module_type not in self.modules:
            logger.error(f"[RequestID: {request_id}] Запрошен несуществующий модуль: {module_name}")
            return {"error": "Модуль не найден"}

        module = self.modules[module_type]
        if not hasattr(module, 'process_request'):
             logger.error(f"[RequestID: {request_id}] У модуля {module_type.value} отсутствует метод process_request")
             return {"error": f"Module {module_type.value} does not have process_request method"}

        # --- Управление сессией на запрос ---
        async with self.get_db_session() as db_session:
            try:
                # Получаем язык пользователя для передачи в модуль
                user_db = (await db_session.execute(select(MubarakUserDB.language).where(MubarakUserDB.user_id == user_id))).scalars().first()
                if user_db:
                    request['user_language'] = user_db

                logger.info(f"[RequestID: {request_id}] Передача запроса в модуль {module_type.value}")
                # Передаем сессию в модуль
                result = await module.process_request(user_id, request, db_session=db_session)
                logger.info(f"[RequestID: {request_id}] Модуль {module_type.value} вернул результат: {result}")

                # Коммитим изменения, если модуль отработал успешно и не вернул ошибку
                if result.get("success"):
                    await db_session.commit()
                else:
                    # Модуль мог вернуть success: False, откатывать транзакцию не обязательно,
                    # так как модуль не должен был делать изменений.
                    await db_session.rollback()

                # TODO: Логику обновления статистики пользователя также нужно перенести сюда
                # await self._update_user_stats(user_id, request_type, result, db_session)

                logger.info(f"[RequestID: {request_id}] Генерация дополнительных рекомендаций")

                # --- Оптимизация создания блоков ---
                # Если в пуле накопилось достаточно транзакций, создаем новый блок
                if len(self.main_ledger.pending_transactions) >= self.BLOCK_CREATION_THRESHOLD:
                    self.logger.info(f"Достигнут порог в {self.BLOCK_CREATION_THRESHOLD} транзакций. Создание нового блока...")
                    self.main_ledger.create_block(proof=random.randint(1, 100000), miner=self.node_identifier)

                additional_recommendations = await self.recommendation_engine.generate_recommendations(
                    user_id, request_type, result
                )
                
                final_response = {
                    **result,
                    "additional_recommendations": additional_recommendations,
                    # "user_stats": await self._get_user_stats(user_id) # Тоже нужно переделать под БД
                }
                logger.info(f"[RequestID: {request_id}] Отправка финального ответа пользователю.")
                return final_response

            except Exception as e:
                # Роллбэк теперь обрабатывается в контекстном менеджере
                logger.exception(f"[RequestID: {request_id}] Критическая ошибка при обработке запроса в модуле {module_type.value} для пользователя {user_id}")
                return {"success": False, "error": "Произошла внутренняя ошибка сервера."}
    
    async def get_daily_dashboard(self, user_id: str) -> Dict[str, Any]:
        """Получение ежедневного дашборда"""
        # TODO: Этот метод также нужно переписать для работы с БД
        # Вместо self.users[user_id] нужно будет делать запрос к БД
        # и передавать сессию в process_request
        async with self.get_db_session() as db_session:
            user_db = (await db_session.execute(select(MubarakUserDB).where(MubarakUserDB.user_id == user_id))).scalars().first()
            if not user_db:
                return {"error": "Пользователь не найден"}

            # --- Оркестрация для сбора контекста ---
            dashboard_context = {
                "db_session": db_session,
                "user_career_level": user_db.career_level
            }
            
            all_recommendations = []
            for module_type, module in self.modules.items():
                try:
                    recs = await module.get_daily_recommendations(user_id, context=dashboard_context)
                    all_recommendations.extend(recs)
                except Exception as e:
                    logger.warning(f"Не удалось получить рекомендации от модуля {module_type.value}: {e}")
                    continue
            
            # ... остальная логика дашборда (требует дальнейшего рефакторинга)
            return {"user_name": user_db.full_name, "recommendations": all_recommendations}
    
    async def get_user_by_api_key(self, api_key: str) -> Optional[str]:
        """Находит user_id по API-ключу."""
        async with self.get_db_session() as db_session:
            stmt = select(MubarakUserDB).where(MubarakUserDB.api_key == api_key)
            user = (await db_session.execute(stmt)).scalars().first()
            return user.user_id if user else None

    async def get_user_by_id(self, user_id: str) -> Optional[MubarakUser]:
        """Находит объект пользователя по ID."""
        # Этот метод возвращает dataclass, а не объект БД, что может быть неверно.
        # Для согласованности лучше работать с объектами БД внутри, а dataclass использовать для API.
        async with self.get_db_session() as db_session:
            stmt = select(MubarakUserDB).where(MubarakUserDB.user_id == user_id)
            user_db = (await db_session.execute(stmt)).scalars().first()
            # Здесь нужно будет преобразовать user_db в MubarakUser (dataclass), если это необходимо
            return user_db # Возвращаем пока объект БД для простоты

    async def get_all_users(self, skip: int = 0, limit: int = 10) -> Tuple[List[Dict], int]:
        """Возвращает страницу со списком всех пользователей и их общее количество."""
        async with self.get_db_session() as db_session:
            count_stmt = select(func.count()).select_from(MubarakUserDB)
            total_count = await db_session.scalar(count_stmt)
            
            users_stmt = select(MubarakUserDB).offset(skip).limit(limit)
            users_db = (await db_session.execute(users_stmt)).scalars().all()
            # Преобразуем объекты БД в словари для ответа API
            paginated_users = [
                {"user_id": u.user_id, "full_name": u.full_name, "email": u.email, "baraka_points": u.baraka_points}
                for u in users_db
            ]
            return paginated_users, total_count


    async def get_module_dashboard(self, user_id: str, module_type: ModuleType) -> Dict[str, Any]:
        """Получение дашборда конкретного модуля"""
        if user_id not in self.users or module_type not in self.modules:
            return {"error": "Не найдено"}
        
        module = self.modules[module_type]
        base_info = {
            "module_name": module_type.value,
            "module_description": self._get_module_description(module_type),
            "user_stats": await self._get_module_user_stats(user_id, module_type),
            "quick_actions": self._get_module_quick_actions(module_type)
        }
        module_data = await module.get_daily_recommendations(user_id)
        related_activities = await self._get_related_activities(user_id, module_type)
        
        return {
            **base_info,
            "module_data": module_data,
            "related_activities": related_activities,
            "achievements": await self._get_module_achievements(user_id, module_type)
        }
    
    async def _generate_welcome_package(self, user: MubarakUser) -> Dict[str, Any]:
        """Генерация приветственного пакета"""
        return {
            "welcome_message": f"""
            Ассаляму алейкум, {user.full_name}!

            Добро пожаловать в MubarakAI - универсальную платформу 
            для современного мусульманина.

            Ваш путь начинается с уровня: {user.get_user_level()}
            Начальные очки бараката: {user.baraka_points}

            Доступные модули:
            1. Fard-AI - Помощник по поклонению
            2. Baitul Hikma - Шариатский аудит
            3. Ar-Rihla - Сообщество знаний  
            4. Ummah Waqf - Цифровые вакфы

            Да поможет вам Аллах на этом пути!
            """,
            "initial_tasks": [
                {"task": "Завершить профиль", "baraka_reward": 10},
                {"task": "Изучить один модуль", "baraka_reward": 20},
                {"task": "Выполнить первую активность", "baraka_reward": 30}
            ],
            "community_links": [
                {"name": "Telegram сообщество", "url": "https://t.me/mubarakai"},
                {"name": "YouTube канал", "url": "https://youtube.com/mubarakai"},
                {"name": "Онлайн-курсы", "url": "https://learn.mubarakai.com"}
            ]
        }
    
    def _detect_initial_roles(self, user_data: Dict) -> List[UserRole]:
        """Определение начальных ролей пользователя"""
        roles = [UserRole.MUSLIM]
        
        # Определение по возрасту и полу
        age = datetime.now().year - user_data['birth_year']
        if 18 <= age <= 30:
            roles.append(UserRole.STUDENT)
        
        # Определение по профессии (в реальности из профиля)
        profession = user_data.get('profession', '').lower()
        if any(word in profession for word in ['teacher', 'учитель', 'преподаватель']):
            roles.append(UserRole.TEACHER)
        
        if any(word in profession for word in ['investor', 'инвестор', 'финанс']):
            roles.append(UserRole.INVESTOR)
        
        # Определение по семейному положению
        if user_data.get('family_status') == 'family':
            roles.append(UserRole.HOST_FAMILY)
        
        # Специальное правило для назначения администратора
        if "admin" in user_data['email']:
            roles.append(UserRole.ADMIN)

        return roles
    
    async def _update_user_stats(self, user_id: str, request_type: str, result: Dict):
        """Обновление статистики пользователя"""
        if user_id not in self.users:
            return
        
        user = self.users[user_id]
        activity_type = self._map_request_to_activity(request_type)
        if activity_type and hasattr(user, 'update_iman_score'):
            # This method is not on the final user model
            # user.update_iman_score(activity_type)
            pass

        if "baraka_points_added" in result:
            user.baraka_points += result["baraka_points_added"]
        if "knowledge_gained" in result:
            user.knowledge_score = min(100, user.knowledge_score + result["knowledge_gained"])
        if "donation_made" in result:
            user.generosity_score = min(100, user.generosity_score + result["donation_made"] * 0.1)
    
    def _map_request_to_activity(self, request_type: str) -> Optional[ActivityType]:
        """Сопоставление типа запроса с активностью"""
        mapping = {
            "prayer_completion": ActivityType.PRAYER,
            "fasting_update": ActivityType.FASTING,
            "learning_update": ActivityType.LEARNING,
            "teaching_session": ActivityType.TEACHING,
            "hosting_request": ActivityType.HOSTING,
            "travel_planning": ActivityType.TRAVELING,
            "investment_made": ActivityType.INVESTING,
            "audit_completed": ActivityType.AUDITING,
            "donation_made": ActivityType.DONATION
        }
        return mapping.get(request_type)
    
    async def _get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Получение статистики пользователя"""
        if user_id not in self.users:
            return {}
        
        user = self.users[user_id]
        return {
            "iman_score": user.iman_score,
            "knowledge_score": user.knowledge_score,
            "generosity_score": user.generosity_score,
            "trust_score": user.trust_score,
            "baraka_points": user.baraka_points,
            "level": user.get_user_level(),
            "activity_stats": user.activity_stats,
            "module_engagement": self._calculate_module_engagement(user_id)
        }
    
    def _calculate_module_engagement(self, user_id: str) -> Dict[str, float]:
        """Расчет вовлеченности в модули"""
        if user_id not in self.sessions:
            return {}
        
        engagement = {}
        for module_type in self.modules.keys(): # pragma: no cover
            engagement[module_type.value] = random.uniform(0.3, 0.9)
        return engagement
    
    def _prioritize_recommendations(self, recommendations: List[Dict]) -> List[Dict]:
        """Приоритизация рекомендаций"""
        priority_weights = {
            "high": 3,
            "medium": 2,
            "low": 1
        }
        
        sorted_recs = sorted(recommendations, 
                           key=lambda x: (priority_weights.get(x.get("priority", "low"), 1), 
                                         random.random()),
                           reverse=True)
        return sorted_recs[:10]  # Не более 10 рекомендаций
    
    async def _calculate_module_synergies(self, user_id: str) -> List[Dict]:
        """Расчет синергий между модулями"""
        synergies = []
        
        module_pairs = [
            (ModuleType.FARD_AI, ModuleType.BAITUL_HIKMA, "Поклонение + Знания"),
            (ModuleType.AR_RIHLA, ModuleType.UMMAH_WAQF, "Путешествия + Вакфы"),
            (ModuleType.FARD_AI, ModuleType.AR_RIHLA, "Поклонение + Сообщество"),
            (ModuleType.BAITUL_HIKMA, ModuleType.UMMAH_WAQF, "Аудит + Инвестиции")
        ]
        
        for mod1, mod2, description in module_pairs:
            synergy_score = self.orchestrator.synergy_matrix.get(
                (mod1, mod2), 
                self.orchestrator.synergy_matrix.get((mod2, mod1), 0.5)
            )
            
            if synergy_score > 0.6:
                synergies.append({
                    "modules": [mod1.value, mod2.value],
                    "description": description,
                    "score": synergy_score,
                    "suggestion": self._get_synergy_suggestion(mod1, mod2)
                })
        
        return synergies[:3]
    
    def _get_synergy_suggestion(self, mod1: ModuleType, mod2: ModuleType) -> str:
        """Получение предложения по синергии"""
        suggestions = {
            (ModuleType.FARD_AI, ModuleType.BAITUL_HIKMA): 
                "Используйте знания из Baitul Hikma для улучшения поклонения",
            (ModuleType.AR_RIHLA, ModuleType.UMMAH_WAQF): 
                "Инвестируйте в вакфы для поддержки путешественников знаний",
            (ModuleType.FARD_AI, ModuleType.AR_RIHLA): 
                "Найдите попутчиков для совместного поклонения",
            (ModuleType.BAITUL_HIKMA, ModuleType.UMMAH_WAQF): 
                "Проверьте вакфы на шариатское соответствие"
        }
        
        return suggestions.get((mod1, mod2), suggestions.get((mod2, mod1), 
                           "Используйте оба модуля для большего эффекта"))
    
    def _calculate_daily_streak(self, user_id: str) -> int:
        """Расчет ежедневной серии активности"""
        # Упрощенная реализация
        return random.randint(1, 30)
    
    def _get_daily_quote(self) -> str:
        """Получение цитаты дня"""
        quotes = [
            "Лучший из вас - изучающий Коран и обучающий ему.",
            "Знание, которое не применяется, подобно дереву без плодов.",
            "Терпение - ключ ко всему благому.",
            "Улыбка брату - садака."
        ]
        return random.choice(quotes)
    
    async def _get_community_activity(self) -> Dict[str, Any]:
        """Получение активности сообщества"""
        return {
            "active_users": len(self.users),
            "recent_activities": [
                {"user": "Ахмед", "activity": "создал вакф", "module": "Ummah Waqf"},
                {"user": "Марьям", "activity": "завершила халяльный аудит", "module": "Baitul Hikma"},
                {"user": "Ибрагим", "activity": "принял гостя", "module": "Ar-Rihla"}
            ],
            "top_contributors": [
                {"name": "Шейх Юсуф", "baraka_points": 1500, "role": "Эксперт"},
                {"name": "Семья Аль-Ансари", "baraka_points": 1200, "role": "Хост"},
                {"name": "Ахмед студент", "baraka_points": 900, "role": "Активный пользователь"}
            ]
        }
    
    def _get_module_description(self, module_type: ModuleType) -> str:
        """Получение описания модуля"""
        descriptions = {
            ModuleType.FARD_AI: "Помощник по выполнению обязательств (фардов) и поклонению",
            ModuleType.BAITUL_HIKMA: "Шариатский аудит и экспертиза для инвестиций",
            ModuleType.AR_RIHLA: "Сообщество путешественников за знаниями",
            ModuleType.UMMAH_WAQF: "Цифровые вакфы и исламские инвестиции"
        }
        return descriptions.get(module_type, "Модуль")
    
    def _get_module_quick_actions(self, module_type: ModuleType) -> List[Dict]:
        """Получение быстрых действий для модуля"""
        actions = {
            ModuleType.FARD_AI: [
                {"action": "mark_prayer", "title": "Отметить намаз", "icon": "🕌"},
                {"action": "learn_today", "title": "Урок дня", "icon": "📚"},
                {"action": "set_reminder", "title": "Напоминание", "icon": "⏰"}
            ],
            ModuleType.BAITUL_HIKMA: [
                {"action": "audit_project", "title": "Проверить проект", "icon": "🔍"},
                {"action": "find_investment", "title": "Найти инвестицию", "icon": "💰"},
                {"action": "ask_scholar", "title": "Спросить ученого", "icon": "👳"}
            ],
            ModuleType.AR_RIHLA: [
                {"action": "find_host", "title": "Найти жилье", "icon": "🏠"},
                {"action": "share_knowledge", "title": "Поделиться знанием", "icon": "🧠"},
                {"action": "join_group", "title": "Вступить в группу", "icon": "👥"}
            ],
            ModuleType.UMMAH_WAQF: [
                {"action": "create_waqf", "title": "Создать вакф", "icon": "🏦"},
                {"action": "invest", "title": "Инвестировать", "icon": "📈"},
                {"action": "donate", "title": "Пожертвовать", "icon": "🤲"}
            ]
        }
        return actions.get(module_type, [])
    
    async def _get_module_user_stats(self, user_id: str, module_type: ModuleType) -> Dict[str, Any]:
        """Получение статистики пользователя по модулю"""
        stats = {
            ModuleType.FARD_AI: {
                "prayers_this_week": random.randint(20, 35),
                "learning_hours": random.randint(5, 20),
                "current_streak": random.randint(1, 30)
            },
            ModuleType.BAITUL_HIKMA: {
                "projects_audited": random.randint(0, 15),
                "expert_rating": random.uniform(4.0, 5.0),
                "halal_investments": random.randint(1, 10)
            },
            ModuleType.AR_RIHLA: {
                "hosting_count": random.randint(0, 5),
                "travels_count": random.randint(0, 3),
                "knowledge_exchanges": random.randint(1, 20)
            },
            ModuleType.UMMAH_WAQF: {
                "waqfs_founded": random.randint(0, 3),
                "total_invested": random.randint(100, 5000),
                "charity_distributed": random.randint(50, 2000)
            }
        }
        return stats.get(module_type, {})
    
    async def _get_related_activities(self, user_id: str, module_type: ModuleType) -> List[Dict]:
        """Получение связанных активностей из других модулей"""
        related = []
        
        if module_type == ModuleType.FARD_AI:
            related.append({
                "module": "Baitul Hikma",
                "activity": "Изучите шариатские основы намаза",
                "relevance": "high"
            })
            related.append({
                "module": "Ar-Rihla",
                "activity": "Найдите попутчиков для коллективного намаза",
                "relevance": "medium"
            })
        
        elif module_type == ModuleType.BAITUL_HIKMA:
            related.append({
                "module": "Ummah Waqf",
                "activity": "Проверьте халяльные вакфы для инвестиций",
                "relevance": "high"
            })
        
        elif module_type == ModuleType.AR_RIHLA:
            related.append({
                "module": "Ummah Waqf",
                "activity": "Поддержите вакфы для путешественников знаний",
                "relevance": "high"
            })
        
        elif module_type == ModuleType.UMMAH_WAQF:
            related.append({
                "module": "Baitul Hikma",
                "activity": "Получите шариатский сертификат для вашего вакфа",
                "relevance": "high"
            })
        
        return related
    
    async def _get_module_achievements(self, user_id: str, module_type: ModuleType) -> List[Dict]:
        """Получение достижений в модуле"""
        achievements = {
            ModuleType.FARD_AI: [
                {"name": "Первый намаз", "earned": True, "date": "2024-01-15"},
                {"name": "Неделя регулярности", "earned": True, "date": "2024-01-22"},
                {"name": "Месяц обучения", "earned": False, "progress": "75%"}
            ],
            ModuleType.BAITUL_HIKMA: [
                {"name": "Первый аудит", "earned": True, "date": "2024-01-20"},
                {"name": "Эксперт месяца", "earned": False, "progress": "60%"}
            ],
            ModuleType.AR_RIHLA: [
                {"name": "Первое гостеприимство", "earned": random.choice([True, False])},
                {"name": "Путешественник знаний", "earned": False, "progress": "40%"}
            ],
            ModuleType.UMMAH_WAQF: [
                {"name": "Первая инвестиция", "earned": True, "date": "2024-01-18"},
                {"name": "Благотворитель месяца", "earned": False, "progress": "30%"}
            ]
        }
        return achievements.get(module_type, [])
    
    async def get_transaction_by_hash(self, tx_hash: str) -> Optional[Dict]:
        """Находит транзакцию в главном реестре по ее хешу."""
        return self.main_ledger.find_transaction(tx_hash)