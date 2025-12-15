import os
import time
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv

from deploy import load_contract_artifact # Импортируем функцию из нашего скрипта деплоя

# --- КОНФИГУРАЦИЯ ТЕСТА ---
load_dotenv()

NODE_PROVIDER_URL = os.getenv("NODE_PROVIDER_URL")

# Используем разные аккаунты для чистоты теста
DEPLOYER_PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY")
BENEFICIARY_PRIVATE_KEY = os.getenv("BENEFICIARY_PRIVATE_KEY") # Ключ исполнителя
DONOR_1_PRIVATE_KEY = os.getenv("DONOR_1_PRIVATE_KEY")
DONOR_2_PRIVATE_KEY = os.getenv("DONOR_2_PRIVATE_KEY")

# Адреса развернутых контрактов (оставьте пустыми для автоматического деплоя)
WAQF_PROJECT_ADDRESS = ""

def main():
    """Основная функция для тестирования жизненного цикла."""
    # --- 1. ПОДГОТОВКА ---
    w3 = Web3(Web3.HTTPProvider(NODE_PROVIDER_URL))
    if not all([DEPLOYER_PRIVATE_KEY, BENEFICIARY_PRIVATE_KEY, DONOR_1_PRIVATE_KEY, DONOR_2_PRIVATE_KEY]):
        print("Ошибка: Установите переменные окружения для всех участников теста в .env файле.")
        return

    deployer = w3.eth.account.from_key(DEPLOYER_PRIVATE_KEY)
    beneficiary = w3.eth.account.from_key(BENEFICIARY_PRIVATE_KEY)
    donor1 = w3.eth.account.from_key(DONOR_1_PRIVATE_KEY)
    donor2 = w3.eth.account.from_key(DONOR_2_PRIVATE_KEY)

    print(f"Deployer: {deployer.address}")
    print(f"Beneficiary: {beneficiary.address}")
    print(f"Donor 1: {donor1.address}")
    print(f"Donor 2: {donor2.address}\n")

    # Убедимся, что у аккаунтов есть немного ETH для газа
    for acc in [deployer, beneficiary, donor1, donor2]:
        balance = w3.eth.get_balance(acc.address)
        print(f"Баланс {acc.address[:10]}...: {w3.from_wei(balance, 'ether')} ETH")
        if balance == 0:
            print(f"ВНИМАНИЕ: Нулевой баланс у {acc.address}. Тест может завершиться ошибкой.")

    # Загружаем ABI контракта
    waqf_abi, _ = load_contract_artifact("WaqfProject")
    
    # Если адрес контракта не указан, можно добавить логику деплоя прямо сюда
    if not WAQF_PROJECT_ADDRESS:
        print("\nАдрес контракта не указан. Пожалуйста, разверните контракт и впишите адрес в скрипт.")
        return

    contract = w3.eth.contract(address=Web3.to_checksum_address(WAQF_PROJECT_ADDRESS), abi=waqf_abi)
    print(f"\nРаботаем с контрактом по адресу: {contract.address}")

    # --- 2. ЭТАП СБОРА СРЕДСТВ (DONATE) ---
    print("\n--- Шаг 2: Пожертвования ---")
    goal_amount = contract.functions.goalAmount().call()
    print(f"Цель сбора: {w3.from_wei(goal_amount, 'ether')} ETH")

    # Донат от первого донора (60% от цели)
    donation1_amount = int(goal_amount * 0.6)
    send_transaction(w3, contract.functions.donate(), donor1, value=donation1_amount)
    print(f"Донор 1 ({donor1.address[:10]}...) внес {w3.from_wei(donation1_amount, 'ether')} ETH")

    # Донат от второго донора (50% от цели)
    donation2_amount = int(goal_amount * 0.5)
    send_transaction(w3, contract.functions.donate(), donor2, value=donation2_amount)
    print(f"Донор 2 ({donor2.address[:10]}...) внес {w3.from_wei(donation2_amount, 'ether')} ETH")

    raised_amount = contract.functions.raisedAmount().call()
    print(f"Собрано: {w3.from_wei(raised_amount, 'ether')} ETH")
    assert raised_amount >= goal_amount
    print("✅ Цель сбора достигнута!")

    # --- 3. ЭТАП ГОЛОСОВАНИЯ (VOTE) ---
    print("\n--- Шаг 3: Голосование за этап 0 ---")
    
    # Голосует донор 1
    send_transaction(w3, contract.functions.voteForMilestone(0), donor1)
    print(f"Донор 1 проголосовал за этап 0.")

    # Проверяем прогресс голосования
    milestone0 = contract.functions.milestones(0).call()
    approval_votes = milestone0[3]
    print(f"Голосов 'за': {w3.from_wei(approval_votes, 'ether')} ETH")
    assert approval_votes == donation1_amount

    # Голосует донор 2
    send_transaction(w3, contract.functions.voteForMilestone(0), donor2)
    print(f"Донор 2 проголосовал за этап 0.")

    milestone0 = contract.functions.milestones(0).call()
    approval_votes = milestone0[3]
    print(f"Голосов 'за': {w3.from_wei(approval_votes, 'ether')} ETH")
    assert approval_votes == donation1_amount + donation2_amount
    print("✅ Порог для голосования (>50%) достигнут!")

    # --- 4. ЭТАП ВЫПЛАТЫ (RELEASE) ---
    print("\n--- Шаг 4: Выплата средств за этап 0 ---")
    beneficiary_balance_before = w3.eth.get_balance(beneficiary.address)
    
    # Выплату может инициировать кто угодно, например, deployer
    send_transaction(w3, contract.functions.releaseMilestoneFunds(0), deployer)
    print("Средства за этап 0 выплачены.")

    # Проверяем баланс бенефициара
    milestone0_amount = milestone0[1]
    beneficiary_balance_after = w3.eth.get_balance(beneficiary.address)
    
    assert beneficiary_balance_after == beneficiary_balance_before + milestone0_amount
    print(f"✅ Баланс бенефициара успешно пополнен на {w3.from_wei(milestone0_amount, 'ether')} ETH.")

    print("\n🎉 Тестирование жизненного цикла успешно завершено!")

def send_transaction(w3, function_call, from_account, value=0):
    """Хелпер для отправки транзакции и ожидания ее подтверждения."""
    tx = function_call.build_transaction({
        'from': from_account.address,
        'nonce': w3.eth.get_transaction_count(from_account.address),
        'value': value,
        'gas': 300000, # С запасом
        'gasPrice': w3.eth.gas_price,
    })
    signed_tx = w3.eth.account.sign_transaction(tx, from_account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt

if __name__ == "__main__":
    main()