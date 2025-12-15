from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas.did import DIDSetDocumentRequestSchema, DIDSetDocumentResponseSchema, DIDProfileSchema
from src.services.blockchain import BlockchainService, get_blockchain_service

router = APIRouter()

@router.post(
    "/document",
    response_model=DIDSetDocumentResponseSchema,
    summary="Создать или обновить DID профиль",
    description="Принимает URI документа профиля (например, из IPFS) и приватный ключ для подписи транзакции."
)
def set_did_document(
    request_data: DIDSetDocumentRequestSchema,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    **Примечание по безопасности:** Передача приватного ключа на сервер небезопасна.
    В реальном приложении транзакция должна подписываться на клиенте.
    """
    try:
        tx_hash = blockchain_service.set_did_document(
            document_uri=request_data.document_uri,
            user_private_key=request_data.user_private_key
        )
        return DIDSetDocumentResponseSchema(transaction_hash=tx_hash)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка при обновлении DID документа: {e}")

@router.get(
    "/{user_address}",
    response_model=DIDProfileSchema,
    summary="Получить DID профиль пользователя",
    description="Возвращает URI документа профиля для указанного Ethereum-адреса."
)
def get_did_profile(
    user_address: str,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    - **user_address**: Ethereum-адрес пользователя, чей профиль нужно получить.
    """
    try:
        document_uri = blockchain_service.get_did_document_uri(user_address)
        if document_uri is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DID профиль для данного адреса не найден.")
        
        return DIDProfileSchema(document_uri=document_uri)
    except Exception as e:
        # Перехватываем HTTPException из предыдущего блока, чтобы не дублировать ошибку
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Ошибка при получении DID профиля: {e}")