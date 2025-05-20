import json, sys
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QLineEdit, QPushButton, QInputDialog,
)
from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtNetwork import QAbstractSocket

SERVER_URL = "ws://localhost:8080/ws"

class ChatWindow(QWidget):
    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.setWindowTitle(f"Tychagram — {username}")
        self.resize(500, 600)

        # UI
        self.messages = QListWidget()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Введите сообщение…")
        self.sendBtn = QPushButton("Отправить")

        h = QHBoxLayout()
        h.addWidget(self.input, 1)
        h.addWidget(self.sendBtn)

        v = QVBoxLayout(self)
        v.addWidget(self.messages, 1)
        v.addLayout(h)

        # WebSocket
        self.ws = QWebSocket()
        self.ws.error.connect(self.on_error)
        self.ws.textMessageReceived.connect(self.on_message)
        self.ws.open(QUrl(f"{SERVER_URL}?user={username}"))

        # Signals
        self.sendBtn.clicked.connect(self.send)
        self.input.returnPressed.connect(self.send)

    # ─── Slots ────────────────────────────────────────────────────────────────
    def send(self):
        text = self.input.text().strip()
        if not text or self.ws.state() != QAbstractSocket.ConnectedState:
            return
        self.ws.sendTextMessage(json.dumps({"from": self.username, "text": text}))
        self.input.clear()

    def on_message(self, raw: str):
        try:
            msg = json.loads(raw)
            self.messages.addItem(f"{msg['from']}: {msg['text']}")
            self.messages.scrollToBottom()
        except (KeyError, json.JSONDecodeError):
            pass  # пропускаем повреждённые пакеты

    def on_error(self, err):
        self.messages.addItem(f"[error] {self.ws.errorString()}")

# ─── main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)

    name, ok = QInputDialog.getText(None, "Login", "Ваше имя:")
    if not ok or not name:
        sys.exit()

    win = ChatWindow(name)
    win.show()
    sys.exit(app.exec_())