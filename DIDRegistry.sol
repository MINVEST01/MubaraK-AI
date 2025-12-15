// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DIDRegistry
 * @dev Простой реестр для управления децентрализованными идентификаторами (DID).
 * Каждый пользователь может зарегистрировать один DID, связанный с его адресом,
 * и управлять документом, описывающим его профиль (например, ссылка на IPFS).
 */
contract DIDRegistry {

    struct Identity {
        address owner;      // Владелец идентификатора
        string documentURI; // URI документа (например, "ipfs://...")
        bool exists;        // Существует ли такой идентификатор
    }

    // Сопоставление адреса кошелька с его идентификатором
    mapping(address => Identity) private identities;

    // Событие, которое генерируется при обновлении документа
    event DIDDocumentUpdated(address indexed owner, string newDocumentURI);

    /**
     * @dev Регистрирует или обновляет URI документа для отправителя транзакции.
     * @param _documentURI Ссылка на JSON-документ профиля в IPFS.
     */
    function setDocument(string memory _documentURI) external {
        Identity storage identity = identities[msg.sender];

        // Если пользователь регистрируется впервые, устанавливаем владельца
        if (!identity.exists) {
            identity.owner = msg.sender;
            identity.exists = true;
        }

        // Обновляем URI и генерируем событие
        identity.documentURI = _documentURI;
        emit DIDDocumentUpdated(msg.sender, _documentURI);
    }

    /**
     * @dev Возвращает URI документа для указанного адреса.
     * @param _owner Адрес пользователя, чей DID нужно получить.
     */
    function getDocumentURI(address _owner) external view returns (string memory) {
        require(identities[_owner].exists, "DIDRegistry: Identity does not exist");
        return identities[_owner].documentURI;
    }

    /**
     * @dev Проверяет, зарегистрирован ли DID для указанного адреса.
     */
    function exists(address _owner) external view returns (bool) {
        return identities[_owner].exists;
    }
}
