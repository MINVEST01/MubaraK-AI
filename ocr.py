import asyncio
from typing import List


class OCREngine:
    """
    Заглушка для сервиса оптического распознавания символов (OCR).
    В реальном приложении здесь будет интеграция с Tesseract, Google Vision AI и т.д.
    """
    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        """
        Извлекает текст из изображения.
        Возвращает симулированный текст для демонстрации.
        """
        await asyncio.sleep(0.5)  # Имитация сетевой задержки

        # Простая проверка, чтобы симулировать разные результаты
        if len(image_bytes) % 2 == 0:
            return "Состав: вода, сахар, кармин (e120), лимонная кислота, ароматизатор идентичный натуральному."
        else:
            return "Ingredients: Wheat flour, water, salt, yeast, mono- and diglycerides of fatty acids. May contain traces of soy."