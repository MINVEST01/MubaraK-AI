from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import List

from src.api.schemas.waqf import WaqfTransactionSchema, DonationRequestSchema, DonationResponseSchema, NftCertificateSchema, RefundRequestSchema, RefundResponseSchema, VoteRequestSchema, VoteResponseSchema, ReleaseFundsRequestSchema, ReleaseFundsResponseSchema, WaqfProjectDetailsSchema, DonorSchema
from src.services.blockchain import BlockchainService, get_blockchain_service
from src.core.websockets import manager # Импортируем наш менеджер

router = APIRouter()

@router.get(
    "/{waqf_id}/transactions",
    response_model=List[WaqfTransactionSchema],
    summary="Получить историю транзакций для Вакф-проекта",
    description="Возвращает список всех транзакций, связанных с конкретным вакф-проектом, для обеспечения полной прозрачности."
)
async def get_waqf_transactions(
    waqf_id: int,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    Эндпоинт для получения истории транзакций пожертвований для вакф-проекта.

    - **waqf_id**: ID вакф-проекта в вашей базе данных.

    Этот эндпоинт обращается к API блокчейн-эксплорера (например, Etherscan)
    для получения списка транзакций для кошелька, связанного с вакф-проектом.
    """
    # 1. По ID вакф-проекта нужно получить из вашей БД адрес его кошелька.
    #    Здесь мы используем заглушку.
    #    waqf_project = await get_waqf_project_from_db(waqf_id)
    #    if not waqf_project:
    #        raise HTTPException(status_code=404, detail="Вакф-проект не найден")
    #    waqf_wallet_address = waqf_project.wallet_address
    waqf_wallet_address = "0x...YOUR_WAQF_PROJECT_WALLET_ADDRESS..." # ЗАГЛУШКА: Замените на реальный адрес

    # 2. Используем сервис для получения транзакций
    transactions = await blockchain_service.get_transactions_for_address(waqf_wallet_address)

    if not transactions:
        raise HTTPException(status_code=404, detail="Транзакции для данного проекта не найдены")

    return transactions

@router.post(
    "/{waqf_id}/donate",
    response_model=DonationResponseSchema,
    summary="Сделать пожертвование в вакф-проект",
    description="Создает и отправляет транзакцию пожертвования в блокчейн для указанного проекта."
)
def make_donation(
    waqf_id: int,
    donation_data: DonationRequestSchema,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    ### Важное замечание о безопасности:
    Этот эндпоинт принимает приватный ключ в теле запроса, что **категорически небезопасно** для реального приложения.
    Он реализован таким образом для упрощения демонстрации.

    **Правильный подход:**
    1. Клиентское приложение (веб-сайт, мобильное приложение) формирует транзакцию.
    2. Пользователь подписывает ее своим ключом с помощью MetaMask или другого кошелька.
    3. Подписанная транзакция отправляется на бэкенд, который просто пересылает (broadcast) ее в сеть.
    """
    # 1. По ID вакф-проекта получаем из БД адрес его смарт-контракта.
    #    Здесь мы используем заглушку.
    #    waqf_project = await get_waqf_project_from_db(waqf_id)
    #    contract_address = waqf_project.contract_address
    contract_address = "0x...YOUR_WAQF_PROJECT_CONTRACT_ADDRESS..." # ЗАГЛУШКА: Замените на адрес контракта

    try:
        # 2. Вызываем сервис для отправки транзакции
        tx_hash = blockchain_service.make_donation(
            contract_address=contract_address,
            amount_in_ether=donation_data.amount_in_ether,
            donor_private_key=donation_data.donor_private_key
        )
        return DonationResponseSchema(transaction_hash=tx_hash)
    except Exception as e:
        # В реальном приложении здесь будет более детальная обработка ошибок
        raise HTTPException(status_code=400, detail=f"Ошибка при отправке транзакции: {e}")

@router.get(
    "/users/{user_id}/certificates",
    response_model=List[NftCertificateSchema],
    summary="Получить NFT-сертификаты пользователя",
    description="Возвращает список всех NFT-сертификатов о пожертвованиях, принадлежащих пользователю."
)
async def get_user_nft_certificates(
    user_id: str,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    Эндпоинт для получения NFT-сертификатов пользователя.

    - **user_id**: ID пользователя в вашей базе данных.
    """
    # 1. По ID пользователя получаем из БД адрес его кошелька.
    #    Здесь мы используем заглушку.
    #    user = await get_user_from_db(user_id)
    #    if not user or not user.wallet_address:
    #        raise HTTPException(status_code=404, detail="Кошелек пользователя не найден")
    #    owner_address = user.wallet_address
    owner_address = "0x...USER_WALLET_ADDRESS..." # ЗАГЛУШКА: Замените на реальный адрес кошелька

    # 2. Получаем адрес контракта NFT-сертификатов из настроек.
    #    Здесь мы используем заглушку.
    #    certificate_contract_address = settings.WAQF_CERTIFICATE_CONTRACT_ADDRESS
    certificate_contract_address = "0x...YOUR_WAQF_CERTIFICATE_CONTRACT_ADDRESS..." # ЗАГЛУШКА

    # 3. Используем сервис для получения списка NFT
    nfts = await blockchain_service.get_nfts_for_owner(owner_address, certificate_contract_address)

    return nfts

@router.post(
    "/{waqf_id}/refund",
    response_model=RefundResponseSchema,
    summary="Запросить возврат средств из вакф-проекта",
    description="Позволяет жертвователю вернуть свои средства, если кампания по сбору не достигла цели в установленный срок."
)
def claim_refund(
    waqf_id: int,
    refund_data: RefundRequestSchema,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    ### Условия для возврата:
    - Срок сбора средств (дедлайн) должен истечь.
    - Целевая сумма не должна быть собрана.

    **Примечание по безопасности:** Как и в случае с пожертвованием, передача приватного ключа на сервер небезопасна и используется здесь для демонстрации.
    """
    # 1. По ID вакф-проекта получаем из БД адрес его смарт-контракта.
    #    Здесь мы используем заглушку.
    #    waqf_project = await get_waqf_project_from_db(waqf_id)
    #    contract_address = waqf_project.contract_address
    contract_address = "0x...YOUR_WAQF_PROJECT_CONTRACT_ADDRESS..." # ЗАГЛУШКА: Замените на адрес контракта

    try:
        # 2. Вызываем сервис для отправки транзакции возврата
        tx_hash = blockchain_service.claim_refund(
            contract_address=contract_address,
            user_private_key=refund_data.user_private_key
        )
        return RefundResponseSchema(transaction_hash=tx_hash)
    except Exception as e:
        # Здесь могут быть специфичные ошибки контракта, например, "Project is not expired"
        raise HTTPException(status_code=400, detail=f"Ошибка при возврате средств: {e}")

@router.post(
    "/{waqf_id}/milestones/{milestone_index}/vote",
    response_model=VoteResponseSchema,
    summary="Проголосовать за выплату по этапу",
    description="Позволяет донору отдать свой голос за одобрение выплаты средств за выполненный этап."
)
def vote_for_milestone(
    waqf_id: int,
    milestone_index: int,
    vote_data: VoteRequestSchema,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    ### Условия для голосования:
    - Проект должен достичь цели сбора (`GoalReached`).
    - Пользователь должен быть донором этого проекта.
    - Пользователь не должен был голосовать за этот этап ранее.
    """
    contract_address = "0x...YOUR_WAQF_PROJECT_CONTRACT_ADDRESS..." # ЗАГЛУШКА

    try:
        tx_hash = blockchain_service.vote_for_milestone(
            contract_address=contract_address,
            milestone_index=milestone_index,
            user_private_key=vote_data.user_private_key
        )
        return VoteResponseSchema(transaction_hash=tx_hash)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка при голосовании: {e}")

@router.post(
    "/{waqf_id}/milestones/{milestone_index}/release",
    response_model=ReleaseFundsResponseSchema,
    summary="Инициировать выплату по этапу",
    description="Финализирует голосование и, в случае успеха, выплачивает средства бенефициару."
)
def release_milestone_funds(
    waqf_id: int,
    milestone_index: int,
    release_data: ReleaseFundsRequestSchema,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    ### Условия для выплаты:
    - За выплату должно проголосовать большинство доноров (более 50% от общей суммы).
    - Все предыдущие этапы должны быть уже оплачены.
    - Эту функцию может вызвать любой пользователь, оплатив газ.
    """
    contract_address = "0x...YOUR_WAQF_PROJECT_CONTRACT_ADDRESS..." # ЗАГЛУШКА

    try:
        tx_hash = blockchain_service.release_milestone_funds(
            contract_address=contract_address,
            milestone_index=milestone_index,
            user_private_key=release_data.user_private_key
        )
        return ReleaseFundsResponseSchema(transaction_hash=tx_hash)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка при выплате по этапу: {e}")

@router.get(
    "/{waqf_id}/details",
    response_model=WaqfProjectDetailsSchema,
    summary="Получить полную информацию о вакф-проекте",
    description="Возвращает текущее состояние проекта, прогресс сбора, дедлайн и информацию по всем этапам, включая статус голосования."
)
def get_waqf_project_details(
    waqf_id: int,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    Этот эндпоинт напрямую читает данные из view-функций смарт-контракта.
    """
    # 1. По ID вакф-проекта получаем из БД адрес его смарт-контракта.
    #    Здесь мы используем заглушку.
    #    waqf_project = await get_waqf_project_from_db(waqf_id)
    #    contract_address = waqf_project.contract_address
    contract_address = "0x...YOUR_WAQF_PROJECT_CONTRACT_ADDRESS..." # ЗАГЛУШКА

    try:
        project_details = blockchain_service.get_project_details(contract_address)
        return project_details
    except Exception as e:
        # Ошибка может возникнуть, если адрес контракта неверный или ABI не соответствует
        raise HTTPException(status_code=500, detail=f"Не удалось получить детали проекта: {e}")

@router.get(
    "/{waqf_id}/donors",
    response_model=List[DonorSchema],
    summary="Получить список доноров проекта",
    description="Возвращает отсортированный список всех доноров и общую сумму их вкладов."
)
def get_project_donors(
    waqf_id: int,
    blockchain_service: BlockchainService = Depends(get_blockchain_service)
):
    """
    Этот эндпоинт сканирует события `DonationReceived` смарт-контракта,
    чтобы составить полный список доноров.
    """
    contract_address = "0x...YOUR_WAQF_PROJECT_CONTRACT_ADDRESS..." # ЗАГЛУШКА

    try:
        donors = blockchain_service.get_project_donors(contract_address, waqf_id)
        if not donors:
            raise HTTPException(status_code=404, detail="Доноры для этого проекта не найдены.")
        return donors
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить список доноров: {e}")

@router.websocket("/ws/{waqf_id}/subscribe")
async def websocket_endpoint(websocket: WebSocket, waqf_id: int):
    """
    WebSocket-эндпоинт для подписки на события вакф-проекта в реальном времени.
    """
    await manager.connect(websocket, waqf_id)
    try:
        # Держим соединение открытым, пока клиент не отключится
        while True:
            # Можно принимать сообщения от клиента, если это необходимо
            # data = await websocket.receive_text()
            # await manager.broadcast_to_project(f"Client #{waqf_id} says: {data}", waqf_id)
            await asyncio.sleep(1) # Просто ждем
    except WebSocketDisconnect:
        manager.disconnect(websocket, waqf_id)
        print(f"Клиент отключился от проекта {waqf_id}")