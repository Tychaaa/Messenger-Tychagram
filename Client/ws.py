import json
from PyQt5.QtCore import QObject, pyqtSignal, QUrl
from PyQt5.QtNetwork import QAbstractSocket
from PyQt5.QtWebSockets import QWebSocket
from constants import SERVER_URL

class WSBridge(QObject):
    """
    Класс-мост между WebSocket-соединением и интерфейсом Qt.
    Преобразует события WebSocket в сигналы Qt, которые можно обрабатывать в UI.
    """

    # Сигналы, которые будут ловить виджеты Qt
    got_packet = pyqtSignal(dict)   # Сигнал, испускается при получении пакета от сервера (dict)
    connected = pyqtSignal()        # Сигнал, испускается при успешном подключении к серверу
    disconnected = pyqtSignal()     # Сигнал, испускается при отключении от сервера

    def __init__(self, username: str, token: str):
        """
        Создаёт и настраивает WebSocket-клиент:
        - подключается к серверу с токеном;
        - обрабатывает полученные сообщения и состояния соединения.
        """
        super().__init__()

        # Создаём объект WebSocket-клиента
        self.ws = QWebSocket()

        # При получении текстового сообщения — преобразуем из JSON и отправляем как сигнал
        self.ws.textMessageReceived.connect(
            lambda raw: self.got_packet.emit(json.loads(raw))
        )

        # Подключаем обработку смены состояния (подключено / отключено и т.п.)
        self.ws.stateChanged.connect(self._state_changed)

        # Открываем соединение с сервером по URL + передаём токен авторизации
        self.ws.open(QUrl(f"{SERVER_URL}?token={token}"))

    def send(self, data: dict) -> bool:
        """
        Отправляет словарь (сообщение) на сервер через WebSocket.
        Возвращает True при успешной отправке, False — если нет подключения.
        """
        # Проверяем, что соединение установлено
        if self.ws.state() != QAbstractSocket.ConnectedState:
            # нет подключения — отправка невозможна
            return False

        # Преобразуем словарь в JSON-строку и отправляем
        self.ws.sendTextMessage(json.dumps(data))
        return True

    def is_connected(self) -> bool:
        """
        Возвращает True, если WebSocket-соединение установлено,
        иначе — False. Удобно для проверки перед отправкой сообщений.
        """
        return self.ws.state() == QAbstractSocket.ConnectedState

    def _state_changed(self, state):
        """
        Внутренний обработчик изменения состояния WebSocket-соединения.
        Излучает соответствующие сигналы Qt:
        - connected → при успешном подключении;
        - disconnected → при разрыве соединения.
        """
        if state == QAbstractSocket.ConnectedState:
            # Соединение успешно установлено
            self.connected.emit()

        elif state == QAbstractSocket.UnconnectedState:
            # Соединение потеряно или закрыто
            self.disconnected.emit()