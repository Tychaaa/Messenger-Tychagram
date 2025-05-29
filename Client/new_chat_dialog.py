from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListView,
    QPushButton, QMessageBox, QFrame
)
from PyQt5.QtGui     import QStandardItemModel, QStandardItem
import requests
from constants import USER_SEARCH_URL, CHAT_CREATE_URL, LIST_VIEW_QSS

class NewChatDialog(QDialog):
    """Диалоговое окно для поиска пользователя и создания нового личного чата."""

    def __init__(self, token: str, parent=None):
        """
        Инициализирует интерфейс создания чата:
        - принимает токен авторизации;
        - создаёт строку поиска и список результатов;
        - оформляет внешний вид;
        - настраивает кнопку «Начать» и обработку поиска.
        """
        super().__init__(parent)
        self.token = token                         # токен авторизации
        self.selected_username = None              # выбранный username

        self.setWindowTitle("Новый чат")
        self.resize(400, 300)

        # Поисковая строка
        self.searchEdit = QLineEdit(self)
        self.searchEdit.setPlaceholderText("Введите имя или username…")

        # Список найденных пользователей
        self.model = QStandardItemModel(self)      # модель данных для отображения
        self.resultView = QListView(self)          # сам виджет со списком
        self.resultView.setModel(self.model)
        self.resultView.clicked.connect(self.on_select)

        # Убираем рамку по умолчанию
        self.resultView.setFrameShape(QFrame.NoFrame)
        # Стили для фонового прямоугольника со скруглениями
        self.resultView.setStyleSheet(LIST_VIEW_QSS)

        # Кнопка «Начать чат»
        self.startBtn = QPushButton("Начать", self)
        self.startBtn.setObjectName("sendBtn")
        self.startBtn.setEnabled(False)                 # пока ничего не выбрано — отключена
        self.startBtn.clicked.connect(self.on_start)

        # Вертикальное размещение всех элементов
        lay = QVBoxLayout(self)
        lay.addWidget(self.searchEdit)
        lay.addWidget(self.resultView, 1)
        lay.addWidget(self.startBtn)

        # Таймер для отложенного поиска (300 мс)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.do_search)
        self.searchEdit.textChanged.connect(lambda _: self.timer.start(300))

    def do_search(self):
        """
        Выполняет поиск пользователей по введённому запросу:
        - если строка пуста, очищает список;
        - иначе отправляет GET-запрос на сервер;
        - обрабатывает ответ и отображает найденных пользователей в списке.
        """
        q = self.searchEdit.text().strip()
        if not q:
            # Если поле пустое — просто очищаем список результатов
            self.model.clear()
            return

        try:
            # Отправляем GET-запрос с параметром q и заголовком авторизации
            r = requests.get(
                USER_SEARCH_URL,
                params={'q': q},
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=5
            )
            r.raise_for_status()    # выбросит исключение, если код ответа не 200
            data = r.json()         # преобразуем JSON-ответ в Python-объект
        except Exception as e:
            # Если что-то пошло не так — показываем ошибку
            QMessageBox.critical(self, "Ошибка поиска", str(e))
            return

        # Проверяем, что сервер вернул список
        users = data if isinstance(data, list) else []

        # Очищаем предыдущие результаты
        self.model.clear()

        # Добавляем каждого найденного пользователя в список
        for u in users:
            username = u.get('username')
            if not username:
                # пропускаем некорректные записи
                continue

            # Показываем либо display_name, либо username
            display = u.get('display_name') or u.get('display') or username
            item = QStandardItem(f"{display} ({username})")
            item.setData(username, Qt.UserRole)
            self.model.appendRow(item)

    def on_select(self, index):
        """
        Обрабатывает выбор пользователя из списка:
        - сохраняет username выбранного пользователя;
        - активирует кнопку «Начать».
        """
        self.selected_username = index.data(Qt.UserRole)
        self.startBtn.setEnabled(True)

    def on_start(self):
        """
        Отправляет запрос на сервер для создания нового чата с выбранным пользователем.
        Если успешно — закрывает диалог.
        """
        if not self.selected_username:
            # ничего не выбрано — ничего не делаем
            return

        try:
            # POST-запрос на создание личного чата
            r = requests.post(
                CHAT_CREATE_URL,
                json={'username': self.selected_username},
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=5
            )
            r.raise_for_status()
        except Exception as e:
            # Ошибка сети или сервера
            QMessageBox.critical(self, "Ошибка создания чата", str(e))
            return
        # Если чат успешно создан — закрываем диалог
        self.accept()