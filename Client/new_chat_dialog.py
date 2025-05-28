# new_chat_dialog.py
from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListView,
    QPushButton, QMessageBox
)
from PyQt5.QtGui     import QStandardItemModel, QStandardItem
import requests
from constants       import USER_SEARCH_URL, CHAT_CREATE_URL

class NewChatDialog(QDialog):
    """Диалог поиска пользователя и создания нового чата."""
    def __init__(self, token: str, parent=None):
        super().__init__(parent)
        self.token = token
        self.selected_username = None

        self.setWindowTitle("Новый чат")
        self.resize(400, 300)

        # Поисковая строка
        self.searchEdit = QLineEdit(self)
        self.searchEdit.setPlaceholderText("Введите имя или username…")

        # Список результатов
        self.model = QStandardItemModel(self)
        self.resultView = QListView(self)
        self.resultView.setModel(self.model)
        self.resultView.clicked.connect(self.on_select)

        # Кнопка «Начать чат»
        self.startBtn = QPushButton("Начать", self)
        self.startBtn.setObjectName("sendBtn")
        self.startBtn.setEnabled(False)
        self.startBtn.clicked.connect(self.on_start)

        # Layout
        lay = QVBoxLayout(self)
        lay.addWidget(self.searchEdit)
        lay.addWidget(self.resultView, 1)
        lay.addWidget(self.startBtn)

        # Дебаунс поиска
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.do_search)
        self.searchEdit.textChanged.connect(lambda _: self.timer.start(300))

    def do_search(self):
        q = self.searchEdit.text().strip()
        if not q:
            # если поле пустое, очищаем результаты поиска
            self.model.clear()
            return

        try:
            r = requests.get(
                USER_SEARCH_URL,
                params={'q': q},
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=5
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка поиска", str(e))
            return

        users = data if isinstance(data, list) else []

        self.model.clear()
        for u in users:
            username = u.get('username')
            if not username:
                continue
            display = u.get('display_name') or u.get('display') or username
            item = QStandardItem(f"{display} ({username})")
            item.setData(username, Qt.UserRole)
            self.model.appendRow(item)

    def on_select(self, index):
        # Включаем кнопку, запоминаем username
        self.selected_username = index.data(Qt.UserRole)
        self.startBtn.setEnabled(True)

    def on_start(self):
        """POST /chats/direct и закрываем диалог"""
        if not self.selected_username:
            return
        try:
            r = requests.post(
                CHAT_CREATE_URL,
                json={'username': self.selected_username},
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=5
            )
            r.raise_for_status()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка создания чата", str(e))
            return
        # Всё ок — закроем и вернём выбранного пользователя
        self.accept()
