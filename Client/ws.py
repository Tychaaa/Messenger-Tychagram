import json
from PyQt5.QtCore import QObject, pyqtSignal, QUrl
from PyQt5.QtNetwork import QAbstractSocket
from PyQt5.QtWebSockets import QWebSocket
from constants import SERVER_URL

# Класс-«мост», чтобы перевести события WebSocket в Qt-сигналы
class WSBridge(QObject):
    # Сигналы, которые будут ловить виджеты Qt
    got_packet = pyqtSignal(dict)   # Сигнал, испускается при получении пакета от сервера (dict)
    connected = pyqtSignal()        # Сигнал, испускается при успешном подключении к серверу
    disconnected = pyqtSignal()     # Сигнал, испускается при отключении от сервера

    # Инициализация WebSocket-соединения и настройка сигналов
    def __init__(self, username: str, token: str):
        super().__init__()

        # Создаём объект WebSocket-клиента
        self.ws = QWebSocket()

        # Каждый полученный текстовый фрейм → превращаем в dict и бросаем сигнал got_packet
        self.ws.textMessageReceived.connect(
            lambda raw: self.got_packet.emit(json.loads(raw))
        )

        # Отслеживаем смену состояния подключения
        self.ws.stateChanged.connect(self._state_changed)

        # Устанавливаем соединение с сервером, передаём имя пользователя
        self.ws.open(QUrl(f"{SERVER_URL}?token={token}"))

    # Отправляет словарь (пакет) как JSON через WebSocket
    def send(self, data: dict) -> bool:
        # Проверяем, установлено ли соединение с сервером
        if self.ws.state() != QAbstractSocket.ConnectedState:
            return False

        # Сериализуем словарь в JSON и отправляем
        self.ws.sendTextMessage(json.dumps(data))
        return True

    # Проверяет, установлено ли соединение с сервером
    def is_connected(self) -> bool:
        return self.ws.state() == QAbstractSocket.ConnectedState

    # Обработка смены состояния соединения (внутренний метод)
    def _state_changed(self, state):
        # Если подключение установлено — испускаем сигнал connected
        if state == QAbstractSocket.ConnectedState:
            self.connected.emit()

        # Если соединение разорвано — испускаем сигнал disconnected
        elif state == QAbstractSocket.UnconnectedState:
            self.disconnected.emit()