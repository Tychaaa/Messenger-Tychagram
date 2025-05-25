import json, sys
from collections import defaultdict
from datetime import datetime

from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QObject, QSize
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QLineEdit, QPushButton, QSplitter, QLabel,
    QInputDialog, QListWidgetItem, QFrame
)
from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtNetwork import QAbstractSocket

# Адрес сервера, к которому подключается клиент по WebSocket
SERVER_URL = "ws://localhost:8080/ws"

# Класс-прокладка, чтобы перевести сигнал WebSocket в формат, удобный для Qt
class WSBridge(QObject):
    got_packet = pyqtSignal(dict)

# Виджет одного сообщения (пузырёк)
class BubbleWidget(QWidget):
    def __init__(self, text: str, outgoing: bool, time_str: str):
        super().__init__()

        # Создаём QLabel с текстом сообщения
        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)                                  # перенос строки по ширине
        lbl_text.setTextInteractionFlags(Qt.TextSelectableByMouse)  # разрешаем выделение текста мышкой
        lbl_text.setStyleSheet("padding:0px; margin:0px;")          # убираем отступы вокруг текста

        # Создаём метку с временем сообщения
        lbl_time = QLabel(time_str)
        lbl_time.setStyleSheet("font-size:11px;")               # небольшой шрифт
        lbl_time.setAlignment(Qt.AlignRight | Qt.AlignBottom)   # правый нижний угол

        # Внутренний контейнер — фон пузырька
        bubble = QFrame()
        bubble_lyt = QVBoxLayout(bubble)                        # вертикальное расположение: сначала текст, потом время
        bubble_lyt.setContentsMargins(10, 6, 10, 6)             # внутренние отступы пузыря
        bubble_lyt.setSpacing(4)                                # расстояние между текстом и временем
        bubble_lyt.addWidget(lbl_text)                          # добавляем текст
        bubble_lyt.addWidget(lbl_time, alignment=Qt.AlignRight) # время справа внизу

        # Настраиваем фон и цвет текста в зависимости от направления (отправитель или получатель)
        if outgoing:
            bubble.setStyleSheet(
                "background:#52b788; color:white; border-radius:10px;"      # зелёный пузырёк
            )
        else:
            bubble.setStyleSheet(
                "background:#ffffff; color:#2d6a4f; border-radius:10px;"    # белый пузырёк
            )

        # Выравниваем пузырёк: входящее — слева, исходящее — справа
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        if outgoing:
            root.addStretch()       # отступ слева
            root.addWidget(bubble)  # сам пузырёк справа
        else:
            root.addWidget(bubble)  # сам пузырёк слева
            root.addStretch()       # отступ справа

    def sizeHint(self):
        # Получаем рекомендуемый размер от текущего layout-а
        sz = self.layout().sizeHint()
        # Возвращаем этот размер, увеличив высоту на 20 пикселей
        return sz + QSize(0, 20)

# Главное окно мессенджера
class ChatWindow(QWidget):
    def __init__(self, username: str):
        super().__init__()
        self.username = username                      # Имя текущего пользователя
        self.recipient = ""                           # Имя собеседника
        self.convs = defaultdict(list)                # История переписок: получатель → список сообщений

        # Настройка окна
        self.setWindowTitle(f"Tychagram — {username}")
        self.resize(700, 500)

        # Список пользователей слева
        self.usersList = QListWidget()
        self.usersList.currentTextChanged.connect(self.switch_chat)

        # Список сообщений справа
        self.messages = QListWidget()
        self.messages.setSpacing(4)                                         # отступ между сообщениями
        self.messages.setSelectionMode(QListWidget.NoSelection)             # запрет выделения мышкой
        self.messages.setVerticalScrollMode(QListWidget.ScrollPerPixel)     # плавная прокрутка

        # Поле ввода и кнопка отправки
        self.input = QLineEdit()
        self.input.setPlaceholderText("Сообщение…")     # серый текст-подсказка
        self.sendBtn = QPushButton("Send")
        self.sendBtn.setObjectName("sendBtn")           # нужен для CSS-стилей
        self.sendBtn.setEnabled(False)                  # заблокирована, пока не выбран собеседник
        self.sendBtn.clicked.connect(self.send)         # обработка клика по кнопке
        self.input.returnPressed.connect(self.send)     # отправка по Enter

        # Компоновка: поле ввода + кнопка в одну строку
        inputBar = QHBoxLayout()
        inputBar.addWidget(self.input, 1)
        inputBar.addWidget(self.sendBtn)

        # Правая часть (чаты): заголовок + сообщения + ввод
        self.chatLabel = QLabel("Выберите собеседника в списке слева")
        right = QVBoxLayout()
        right.addWidget(self.chatLabel)      # имя собеседника или подсказка
        right.addWidget(self.messages, 1)    # список сообщений
        right.addLayout(inputBar)            # поле + кнопка
        rightBox = QWidget()
        rightBox.setLayout(right)

        # Основной делитель экрана: слева список пользователей, справа чат
        splitter = QSplitter()
        splitter.addWidget(self.usersList)
        splitter.addWidget(rightBox)
        splitter.setStretchFactor(1, 1)

        # Устанавливаем главный layout окна
        main = QVBoxLayout(self)
        main.addWidget(splitter)

        # Применяем стили (цвета, шрифты)
        self.apply_style()

        # WebSocket: создаём соединение с сервером
        self.ws = QWebSocket()
        self.bridge = WSBridge()    # «мост» между WebSocket и Qt-сигналами

        # Полученные данные обрабатываем через bridge.got_packet
        self.ws.textMessageReceived.connect(
            lambda raw: self.bridge.got_packet.emit(json.loads(raw))
        )
        self.bridge.got_packet.connect(self.handle_packet)

        # Открываем соединение с сервером и передаём имя пользователя
        self.ws.open(QUrl(f"{SERVER_URL}?user={username}"))

    # Стилизация пастельно-зелёной темой
    def apply_style(self):
        pastel_qss = """
        QWidget {
            background-color: #e9f5ef;
            color: #2d6a4f;
            font-family: "Segoe UI", "Inter", sans-serif;
            font-size: 14px;
        }
        QSplitter::handle { background-color: #b7e4c7; }
        QListWidget {
            background: #d8f3dc;
            border: none;
        }
        QListWidget::item { padding: 6px 10px; }
        QListWidget::item:selected {
            background: #b7e4c7;
            color: #1b4332;
        }
        QListWidget::item:hover { background: #c9ecd2; }
        QPushButton#sendBtn {
            background-color: #52b788;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 6px 14px;
        }
        QPushButton#sendBtn:hover   { background-color: #40916c; }
        QPushButton#sendBtn:disabled{
            background-color: #95d5b2;
            color: #e9f5ef;
        }
        QLineEdit {
            background: #ffffff;
            border: 1px solid #b7e4c7;
            border-radius: 6px;
            padding: 6px 8px;
        }
        """
        # Применяем стили ко всему окну и вложенным элементам
        self.setStyleSheet(pastel_qss)

    # Вызывается при выборе пользователя в списке.
    # Обновляет заголовок чата, активирует поле ввода и загружает историю переписки.
    def switch_chat(self, text: str):
        # Если строка пустая (ничего не выбрано) — ничего не делаем
        if not text:
            return

        # Извлекаем имя пользователя (без индикатора ●)
        self.recipient = text.split()[0]
        # Отображаем имя выбранного собеседника над чат-окном
        self.chatLabel.setText(self.recipient)
        # Разблокируем кнопку "Send", теперь можно отправлять сообщения
        self.sendBtn.setEnabled(True)
        # Загружаем историю переписки с этим пользователем
        self.reload_chat_view()

        # Убираем зелёную точку "непрочитано" у выбранного пользователя
        for i in range(self.usersList.count()):
            itm = self.usersList.item(i)
            if itm.text().split()[0] == self.recipient:
                itm.setText(self.recipient)
                break

    # Отправляет сообщение выбранному собеседнику через WebSocket
    def send(self):
        # Получаем текст из поля ввода и убираем лишние пробелы
        text = self.input.text().strip()

        # Если сообщение пустое, нет выбранного получателя
        # или WebSocket не подключён — ничего не делаем
        if not text or not self.recipient or self.ws.state() != QAbstractSocket.ConnectedState:
            return

        # Формируем словарь-сообщение (пакет) с нужными данными
        pkt = {
            "type": "msg",               # тип пакета — сообщение
            "from": self.username,       # имя отправителя
            "to": self.recipient,        # имя получателя
            "text": text                 # текст сообщения
        }

        # Отправляем JSON-пакет через WebSocket на сервер
        self.ws.sendTextMessage(json.dumps(pkt))
        # Очищаем поле ввода после отправки
        self.input.clear()

    # Обработка входящих/исходящих пакетов
    def handle_packet(self, pkt: dict):
        ptype = pkt.get("type") # Определяем тип пакета

        # Если это пакет со списком пользователей — обновляем список слева
        if ptype == "users":
            self.update_users(pkt["users"])
            return

        # Если это сообщение — добавляем его в переписку
        if ptype == "msg":
            time_now = datetime.now().strftime("%H:%M") # Текущее время для отображения

            # Определяем, с кем переписка (если мы получатель, то peer = отправитель, и наоборот)
            peer = pkt["from"] if pkt["from"] != self.username else pkt["to"]
            # Добавляем сообщение в историю переписки с этим пользователем
            self.convs[peer].append((pkt["from"], pkt["text"], time_now))

            # Если сейчас открыт чат с этим пользователем — сразу отображаем сообщение
            if peer == self.recipient:
                self.add_bubble(pkt["from"], pkt["text"], time_now)
            else:
                # Иначе — помечаем, что есть непрочитанное сообщение
                self.highlight_user(peer)

    # Рендер пузырька в messages-листе
    def add_bubble(self, sender: str, text: str, time_str: str):
        outgoing = sender == self.username                  # Проверяем, наше ли это сообщение
        bubble = BubbleWidget(text, outgoing, time_str)     # Создаём виджет-пузырёк

        # Создаём элемент списка, к которому прикрепим наш пузырёк
        item = QListWidgetItem()
        self.messages.addItem(item)                 # Добавляем элемент в QListWidget (messages)
        self.messages.setItemWidget(item, bubble)   # Прикрепляем к элементу виджет-пузырёк

        # Устанавливаем высоту строки на основе содержимого пузырька
        item.setSizeHint(bubble.sizeHint())
        # Автоматическая прокрутка вниз — чтобы было видно новое сообщение
        self.messages.scrollToBottom()

    # Обновляет список онлайн-пользователей
    def update_users(self, users):
        # Сохраняем имя текущего выбранного собеседника (если он был)
        cur_item = self.usersList.currentItem()
        current = cur_item.text() if cur_item else ""

        # Очищаем список и добавляем только других пользователей (без самого себя)
        self.usersList.clear()
        for u in sorted(users):
            if u != self.username:
                self.usersList.addItem(u)

        # Если текущий собеседник всё ещё онлайн — восстанавливаем выделение
        items = self.usersList.findItems(current, Qt.MatchExactly)
        self.usersList.setCurrentItem(items[0] if items else None)

        # Если выбранного собеседника больше нет в списке
        if not items:
            self.recipient = ""
            self.chatLabel.setText("Выберите собеседника в списке слева")
            self.messages.clear()
            self.sendBtn.setEnabled(False)

    # Загружает переписку с выбранным пользователем
    def reload_chat_view(self):
        self.messages.clear()   # Очищаем текущее окно чата
        # Для каждого сообщения в истории текущего собеседника
        for frm, txt, tm in self.convs[self.recipient]:
            self.add_bubble(frm, txt, tm)   # Добавляем пузырёк в интерфейс

    # Помечает пользователя в списке, у которого есть новое непрочитанное сообщение
    def highlight_user(self, user):
        for i in range(self.usersList.count()):
            itm = self.usersList.item(i)
            # Сравниваем имена без символов
            if itm.text().split()[0] == user and not itm.text().endswith(" ●"):
                itm.setText(f"{user} ●")      # зелёная точка «непрочитано»
                break


# Запуск приложения
if __name__ == "__main__":
    app = QApplication(sys.argv)
    name, ok = QInputDialog.getText(None, "Login", "Ваше имя:")
    if not ok or not name.strip():
        sys.exit()
    win = ChatWindow(name.strip())
    win.show()
    sys.exit(app.exec_())