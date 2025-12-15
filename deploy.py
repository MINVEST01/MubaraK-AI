import json
import os
import sys
from pathlib import Path

from web3 import Web3

# --- КОНФИГУРАЦИЯ ---
# Загрузка переменных из .env файла (требуется `pip install python-dotenv`)
from dotenv import load_dotenv
load_dotenv()

NODE_PROVIDER_URL = os.getenv("NODE_PROVIDER_URL") # Например, "https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID"
DEPLOYER_PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY") # Приватный ключ кошелька для оплаты газа

# Параметры для контракта WaqfProject
WAQF_BENEFICIARY_ADDRESS = "0x...YOUR_BENEFICIARY_WALLET_ADDRESS..." # Адрес исполнителя проекта
WAQF_DURATION_IN_DAYS = 30 # Длительность кампании по сбору средств в днях

WAQF_MILESTONES = {
    "descriptions": ["Закупка материалов для фундамента", "Оплата работы строителей (первый этап)"],
    "amounts_in_ether": ["0.005", "0.005"]
}

# Метаданные для NFT
NFT_TOKEN_URI = "ipfs://bafkreihdwd.../metadata.json" # Замените на ваш реальный URI из Pinata/NFT.Storage

# --- КОНЕЦ КОНФИГУРАЦИИ ---

def load_contract_artifact(name: str) -> tuple[str, str]:
    """Загружает ABI и байт-код из файла артефакта."""
    # Указываем путь к артефактам относительно текущего скрипта
    artifact_path = Path(__file__).parent.parent / "src" / "contracts" / f"{name}.json"
    if not artifact_path.exists():
        print(f"Ошибка: Файл артефакта не найден по пути {artifact_path}")
        sys.exit(1)
        
    with open(artifact_path, "r") as f:
        artifact = json.load(f)
    return artifact["abi"], artifact["bytecode"]

def deploy_contract(w3: Web3, deployer_account, contract_abi, contract_bytecode, *args):
    """Универсальная функция для развертывания контракта."""
    Contract = w3.eth.contract(abi=contract_abi, bytecode=contract_bytecode)
    
    # 1. Строим транзакцию для деплоя
    construct_txn = Contract.constructor(*args).build_transaction({
        'from': deployer_account.address,
        'nonce': w3.eth.get_transaction_count(deployer_account.address),
        'gasPrice': w3.eth.gas_price,
    })

    # 2. Подписываем транзакцию
    signed_txn = w3.eth.account.sign_transaction(construct_txn, private_key=deployer_account.key)

    # 3. Отправляем транзакцию
    print(f"Отправка транзакции для развертывания контракта...")
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    
    # 4. Ожидаем подтверждения транзакции и получаем адрес контракта
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = tx_receipt['contractAddress']
    print(f"Контракт успешно развернут! Адрес: {contract_address}")
    return contract_address

def main():
    """Основная функция скрипта."""
    if not NODE_PROVIDER_URL or not DEPLOYER_PRIVATE_KEY:
        print("Ошибка: Установите переменные окружения NODE_PROVIDER_URL и DEPLOYER_PRIVATE_KEY.")
        return

    w3 = Web3(Web3.HTTPProvider(NODE_PROVIDER_URL))
    if not w3.is_connected():
        print("Ошибка: Не удалось подключиться к узлу Ethereum.")
        return

    deployer_account = w3.eth.account.from_key(DEPLOYER_PRIVATE_KEY)
    print(f"Скрипт запущен от имени кошелька: {deployer_account.address}")

    # --- Шаг 1: Развертывание контракта WaqfCertificate ---
    print("\n--- Шаг 1: Развертывание контракта для NFT-сертификатов (WaqfCertificate) ---")
    cert_abi, cert_bytecode = load_contract_artifact("WaqfCertificate")
    # В конструктор передаем владельца - наш аккаунт, который развертывает контракт
    certificate_contract_address = deploy_contract(w3, deployer_account, cert_abi, cert_bytecode, deployer_account.address)

    # --- Шаг 2: Развертывание контракта WaqfProject ---
    print("\n--- Шаг 2: Развертывание основного контракта проекта (WaqfProject) ---")
    waqf_abi, waqf_bytecode = load_contract_artifact("WaqfProject")
    duration_in_seconds = WAQF_DURATION_IN_DAYS * 24 * 60 * 60
    milestone_descriptions = WAQF_MILESTONES["descriptions"]
    milestone_amounts_in_wei = [w3.to_wei(amount, 'ether') for amount in WAQF_MILESTONES["amounts_in_ether"]]

    waqf_project_address = deploy_contract(
        w3, deployer_account, waqf_abi, waqf_bytecode,
        Web3.to_checksum_address(WAQF_BENEFICIARY_ADDRESS),
        duration_in_seconds,
        milestone_descriptions,
        milestone_amounts_in_wei,
        Web3.to_checksum_address(certificate_contract_address),
        NFT_TOKEN_URI
    )

    # --- Шаг 3: Связывание контрактов ---
    print("\n--- Шаг 3: Предоставление прав контракту WaqfProject на выпуск NFT ---")
    certificate_contract = w3.eth.contract(address=certificate_contract_address, abi=cert_abi)
    
    # Вызываем функцию `setWaqfProjectContract`, чтобы разрешить нашему проекту выпускать NFT
    tx = certificate_contract.functions.setWaqfProjectContract(Web3.to_checksum_address(waqf_project_address)).build_transaction({
        'from': deployer_account.address,
        'nonce': w3.eth.get_transaction_count(deployer_account.address),
    })
    signed_tx = w3.eth.account.sign_transaction(tx, DEPLOYER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print("Отправка транзакции для связывания контрактов...")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Контракты успешно связаны!")

    print("\n--- Развертывание завершено! ---")
    print(f"Адрес контракта WaqfProject: {waqf_project_address}")
    print(f"Адрес контракта WaqfCertificate: {certificate_contract_address}")

if __name__ == "__main__":
    main()