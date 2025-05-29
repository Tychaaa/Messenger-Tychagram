from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListView, QPushButton, QLabel, QMessageBox
)
from PyQt5.QtGui     import QStandardItemModel, QStandardItem
import requests
from constants       import USER_SEARCH_URL, GROUP_CREATE_URL

class NewGroupDialog(QDialog):
    """Диалог создания группового чата: название + участники."""
    def __init__(self, token: str, parent=None):
        super().__init__(parent)
        self.token = token
        self.selected = set()  # множ. выбранных username

        self.setWindowTitle("Новый групповой чат")
        self.resize(450, 400)

        # 1) Поле для названия группы
        lbl = QLabel("Название группы:")
        self.nameEdit = QLineEdit(self)
        self.nameEdit.setPlaceholderText("Введите название…")

        # 2) Поисковая строка участников
        lbl2 = QLabel("Добавить участников:")
        self.searchEdit = QLineEdit(self)
        self.searchEdit.setPlaceholderText("Поиск по имени или username…")
        self.searchTimer = QTimer(self)
        self.searchTimer.setSingleShot(True)
        self.searchTimer.timeout.connect(self.do_search)
        self.searchEdit.textChanged.connect(lambda _: self.searchTimer.start(300))

        # 3) Список результатов (с возможностью мн. выбора)
        self.model = QStandardItemModel(self)
        self.view  = QListView(self)
        self.view.setModel(self.model)
        self.view.setSelectionMode(QListView.MultiSelection)
        self.view.clicked.connect(self.on_select)

        # 4) Кнопки
        btnBox = QHBoxLayout()
        self.cancelBtn = QPushButton("Отмена")
        self.okBtn     = QPushButton("Создать")
        self.okBtn.setObjectName("sendBtn")
        self.cancelBtn.setObjectName("sendBtn")
        self.okBtn.setEnabled(False)
        self.cancelBtn.clicked.connect(self.reject)
        self.okBtn.clicked.connect(self.on_create)
        btnBox.addStretch()
        btnBox.addWidget(self.cancelBtn)
        btnBox.addWidget(self.okBtn)

        # Layout всего диалога
        lay = QVBoxLayout(self)
        lay.addWidget(lbl)
        lay.addWidget(self.nameEdit)
        lay.addSpacing(8)
        lay.addWidget(lbl2)
        lay.addWidget(self.searchEdit)
        lay.addWidget(self.view, 1)
        lay.addLayout(btnBox)

    def do_search(self):
        q = self.searchEdit.text().strip()
        if not q:
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
            display  = u.get('display_name') or username
            item = QStandardItem(f"{display} ({username})")
            item.setData(username, Qt.UserRole)
            item.setCheckable(True)
            self.model.appendRow(item)

    def on_select(self, index):
        username = index.data(Qt.UserRole)
        item = self.model.itemFromIndex(index)
        if item.checkState() == Qt.Checked:
            self.selected.add(username)
        else:
            self.selected.discard(username)
        # Активируем кнопку OK, если есть название и хотя бы 1 участник
        self.okBtn.setEnabled(bool(self.selected) and bool(self.nameEdit.text().strip()))

    def on_create(self):
        title = self.nameEdit.text().strip()
        if not title or not self.selected:
            return
        payload = {
            'title': title,
            'usernames': list(self.selected)
        }
        try:
            r = requests.post(
                GROUP_CREATE_URL,
                json=payload,
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=5
            )
            r.raise_for_status()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка создания группы", str(e))
            return
        self.accept()