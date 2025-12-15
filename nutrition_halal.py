from fastapi import APIRouter, Depends, File, UploadFile

from api.security import get_current_user_id_from_key
from core.dependencies import get_mubarak_ai_instance
from core.main_app import MubarakAI
from core.exceptions import DetailedHTTPException
from models import ModuleType

router = APIRouter(tags=["Nutrition Halal"])


@router.post("/nutrition-halal/check-photo")
async def check_product_by_photo(
    user_id: str = Depends(get_current_user_id_from_key),
    file: UploadFile = File(..., description="Фотография состава продукта"),
    mubarakai: MubarakAI = Depends(get_mubarak_ai_instance),
):
    """Проверяет состав продукта на халяльность по фотографии."""
    request = {"module": ModuleType.NUTRITION_HALAL.value, "type": "check_product_photo", "file_content": await file.read(), "filename": file.filename, "content_type": file.content_type}
    result = await mubarakai.process_request(user_id, request)
    if not result.get("success"):
        status_code = 422 if "Ошибка обработки изображения" in result.get("error", "") else 400
        raise DetailedHTTPException(status_code=status_code, error_code="OCR_FAILED", detail=result.get("error") or result.get("message"))
    return result