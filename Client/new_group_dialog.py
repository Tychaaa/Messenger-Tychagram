from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListView, QPushButton, QLabel, QMessageBox, QFrame
)
from PyQt5.QtGui     import QStandardItemModel, QStandardItem
import requests
from constants import USER_SEARCH_URL, GROUP_CREATE_URL, GROUP_MEMBER_LIST_QSS

class NewGroupDialog(QDialog):
    """Диалог создания группового чата: ввод названия и выбор участников."""

    def __init__(self, token: str, parent=None):
        """
        Инициализирует окно создания группы:
        - сохраняет токен авторизации;
        - создаёт поле для ввода названия группы;
        - добавляет поиск пользователей и список для выбора;
        - оформляет кнопки управления и подключает обработчики.
        """
        super().__init__(parent)
        self.token = token

        # Храним выбранных пользователей:
        self.selected = set()               # выбранные username
        self.selected_display = {}          # username → display_name (для показа)

        self.setWindowTitle("Новый групповой чат")
        self.resize(450, 400)

        # 1) Название группы
        lbl_name = QLabel("Название группы:")
        self.nameEdit = QLineEdit(self)
        self.nameEdit.setPlaceholderText("Введите название…")

        # Включаем кнопку «Создать», если есть название и хотя бы один участник
        self.nameEdit.textChanged.connect(
            lambda text: self.okBtn.setEnabled(bool(text.strip()) and bool(self.selected))
        )

        # 2) Поле поиска участников
        lbl_search = QLabel("Добавить участников:")
        self.searchEdit = QLineEdit(self)
        self.searchEdit.setPlaceholderText("Поиск по имени или username…")

        # Настраиваем отложенный вызов поиска (дебаунс)
        self.searchTimer = QTimer(self)
        self.searchTimer.setSingleShot(True)
        self.searchTimer.timeout.connect(self.do_search)
        self.searchEdit.textChanged.connect(lambda _: self.searchTimer.start(300))

        # 3) Список найденных пользователей (можно отмечать несколько)
        self.model = QStandardItemModel(self)
        self.view = QListView(self)
        self.view.setModel(self.model)
        self.view.setSelectionMode(QListView.MultiSelection)
        self.view.clicked.connect(self.on_select)

        # Оформление списка
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setStyleSheet(GROUP_MEMBER_LIST_QSS)

        # 4) Кнопки управления (Отмена и Создать)
        self.cancelBtn = QPushButton("Отмена", self)
        self.cancelBtn.setObjectName("sendBtn")
        self.cancelBtn.clicked.connect(self.reject)     # Закрывает окно без создания

        self.okBtn = QPushButton("Создать", self)
        self.okBtn.setObjectName("sendBtn")
        self.okBtn.setEnabled(False)
        self.okBtn.clicked.connect(self.on_create)      # Обработчик создания чата

        # Кнопки размещаем справа
        btnBox = QHBoxLayout()
        btnBox.addStretch()
        btnBox.addWidget(self.cancelBtn)
        btnBox.addWidget(self.okBtn)

        # Общая компоновка элементов окна
        lay = QVBoxLayout(self)
        lay.addWidget(lbl_name)
        lay.addWidget(self.nameEdit)
        lay.addSpacing(8)
        lay.addWidget(lbl_search)
        lay.addWidget(self.searchEdit)
        lay.addWidget(self.view, 1)
        lay.addLayout(btnBox)

    def do_search(self):
        """
        Выполняет поиск пользователей по введённому запросу:
        - если поле пустое — отображает только уже выбранных;
        - иначе отправляет запрос к серверу и отображает найденных;
        - в списке можно отметить нескольких участников галочками.
        """
        q = self.searchEdit.text().strip()

        # Начинаем с очистки предыдущих результатов
        self.model.clear()

        # Если поле поиска пустое
        if not q:
            # Показываем только уже выбранных участников
            for username in sorted(self.selected):
                # Показываем отображаемое имя (если есть) или username
                display = self.selected_display.get(username, username)
                item = QStandardItem(f"{display} ({username})")
                item.setData(username, Qt.UserRole)
                item.setCheckable(True)
                item.setCheckState(Qt.Checked)
                self.model.appendRow(item)
            return

        # Поиск пользователей на сервере
        try:
            r = requests.get(
                USER_SEARCH_URL,
                params={'q': q},
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=5
            )
            r.raise_for_status()    # выбрасывает исключение, если код ответа не 200
            data = r.json()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка поиска", str(e))
            return

        # Проверяем, что ответ от сервера — это список.
        # Если по какой-то причине это не список (например, словарь с ошибкой) — подставляем пустой список.
        users = data if isinstance(data, list) else []

        # Сначала показываем выбранных пользователей
        for username in sorted(self.selected):
            display = self.selected_display.get(username, username)
            item = QStandardItem(f"{display} ({username})")
            item.setData(username, Qt.UserRole)
            item.setCheckable(True)
            item.setCheckState(Qt.Checked)
            self.model.appendRow(item)

        # Затем — всех новых найденных, которые ещё не выбраны
        for u in users:
            username = u.get('username')
            if not username or username in self.selected:
                # пропускаем повторы
                continue

            display = u.get('display_name') or username
            item = QStandardItem(f"{display} ({username})")
            item.setData(username, Qt.UserRole)
            item.setCheckable(True)
            item.setCheckState(Qt.Unchecked)
            self.model.appendRow(item)

    def on_select(self, index):
        """
        Обрабатывает клик по пользователю в списке:
        - если пользователь отмечен галочкой — добавляем его в список участников;
        - если галочка снята — убираем из выбранных и удаляем из списка;
        - при каждом изменении проверяем, можно ли активировать кнопку «Создать».
        """
        username = index.data(Qt.UserRole)      # Получаем username из выбранной строки
        item = self.model.itemFromIndex(index)  # Получаем сам элемент модели

        if item.checkState() == Qt.Checked:
            # Пользователь выбран (отмечен галочкой)
            self.selected.add(username)                             # Добавляем в множество выбранных
            display = item.text().rsplit(" (", 1)[0]   # Получаем отображаемое имя
            self.selected_display[username] = display               # Сохраняем его для отображения
        else:
            # Пользователь снят (убран из выбранных)
            self.selected.discard(username)             # Удаляем из множества
            self.selected_display.pop(username, None)   # Удаляем отображаемое имя
            self.model.removeRow(index.row())           # Удаляем строку из списка

        # Проверяем, можно ли включить кнопку «Создать»:
        # для этого нужно, чтобы было введено название и выбран хотя бы один участник
        has_name = bool(self.nameEdit.text().strip())
        self.okBtn.setEnabled(has_name and bool(self.selected))

    def on_create(self):
        """
        Отправляет запрос на создание группового чата:
        - собирает название и список участников;
        - делает POST-запрос к серверу;
        - если всё успешно — закрывает окно.
        """
        title = self.nameEdit.text().strip()

        # Проверка: нужно название и хотя бы один участник
        if not title or not self.selected:
            return

        # Подготавливаем данные для отправки
        payload = {
            'title': title,
            'usernames': list(self.selected)
        }
        try:
            # Отправляем запрос на сервер
            r = requests.post(
                GROUP_CREATE_URL,
                json=payload,
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=5
            )
            r.raise_for_status()    # выбрасывает исключение, если код ответа не 200
        except Exception as e:
            # При ошибке показываем сообщение
            QMessageBox.critical(self, "Ошибка создания группы", str(e))
            return

        # Группа успешно создана — закрываем диалог
        self.accept()