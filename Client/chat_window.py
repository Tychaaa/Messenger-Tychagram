import time
from collections    import defaultdict
from datetime       import datetime, timezone

from PyQt5.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QVBoxLayout, QSplitter, QListView, QDialog
)

from constants  import PASTEL_QSS
from models     import ChatListModel, ChatSummary
from new_chat_dialog import NewChatDialog
from ws         import WSBridge
from widgets    import BubbleWidget, ChatItemDelegate


# Главное окно мессенджера
class ChatWindow(QWidget):
    def __init__(self, username: str, token: str):
        super().__init__()
        self.username = username                      # Имя текущего пользователя
        self.token = token
        self.recipient = ""                           # Имя собеседника
        self.convs = defaultdict(list)                # История переписок: получатель → список сообщений

        # Настройка окна
        self.setWindowTitle(f"Tychagram — {username}")
        self.resize(900, 600)

        # Список пользователей слева
        self.newChatBtn = QPushButton("Новый чат")
        self.newChatBtn.setObjectName("sendBtn")
        self.newChatBtn.clicked.connect(self.open_new_chat)

        self.chatModel = ChatListModel(self)
        self.chatListView = QListView()
        self.chatListView.setModel(self.chatModel)
        self.chatListView.setItemDelegate(ChatItemDelegate(self.chatListView))
        self.chatListView.setSpacing(2)  # небольшие промежутки между карточками
        self.chatListView.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.chatListView.setStyleSheet(
            "QListView{background:transparent;border:none;}"
        )
        self.chatListView.clicked.connect(self.on_chat_selected)

        leftBox = QWidget()
        leftLay = QVBoxLayout(leftBox)
        leftLay.setContentsMargins(0, 0, 0, 0)
        leftLay.addWidget(self.newChatBtn)
        leftLay.addWidget(self.chatListView, 1)

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
        splitter.addWidget(leftBox)
        splitter.addWidget(rightBox)
        splitter.setStretchFactor(1, 1)

        # Устанавливаем главный layout окна
        main = QVBoxLayout(self)
        main.addWidget(splitter)

        # Применяем стили (цвета, шрифты)
        self.setStyleSheet(PASTEL_QSS)

        # WebSocket: создаём соединение с сервером
        self.ws_bridge = WSBridge(username, token)
        self.ws_bridge.got_packet.connect(self.handle_packet)

    def open_new_chat(self):
        dlg = NewChatDialog(self.token, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            # после успешного создания чат-лист придёт по WS push
            pass

    # Вызывается при выборе пользователя в списке.
    # Обновляет заголовок чата, активирует поле ввода и загружает историю переписки.
    def on_chat_selected(self, index):
        """Обработка клика по диалогу в списке"""
        username = self.chatModel.data(index, ChatListModel.UsernameRole)
        self.recipient = username
        display  = self.chatModel.data(index, ChatListModel.DisplayRole)
        self.chatLabel.setText(display)
        self.sendBtn.setEnabled(True)
        self.reload_chat_view()

    # Отправляет сообщение выбранному собеседнику через WebSocket
    def send(self):
        # Получаем текст из поля ввода
        txt = self.input.text().strip()

        # Если сообщение пустое или не выбран получатель — выходим
        if not txt or not self.recipient:
            return

        # Формируем словарь-пакет с типом "msg" и основными полями
        self.ws_bridge.send({
            "type": "msg",
            "from": self.username,
            "to": self.recipient,
            "text": txt
        })

        # Очищаем поле ввода после отправки
        self.input.clear()

    # Обработка входящих/исходящих пакетов
    def handle_packet(self, pkt: dict):
        ptype = pkt.get("type") # Определяем тип пакета

        if ptype == "history":
            chat_id = pkt.get("chat_id")  # безопаснее через .get
            # Берём список сообщений, или пустой список, если его нет
            messages = pkt.get("messages") or []
            last_peer = None
            for row in messages:
                dt = datetime.fromtimestamp(row.get("ts", 0) / 1000,
                                            timezone.utc).astimezone()
                hhmm = dt.strftime("%H:%M")
                peer = row.get("from") if row.get("from") != self.username else row.get("to")
                # сохраняем peer последнего сообщения
                last_peer = peer
                self.convs[peer].append((row.get("from"), row.get("text"), hhmm))
            # Перерисовываем только если были сообщения и чат открыт
            if last_peer and self.recipient == last_peer:
                self.reload_chat_view()
            return

        # Если это пакет со списком пользователей — обновляем список слева
        if ptype == "chats":
            raw = pkt.get("chats", [])
            chats = []
            for c in raw:
                chats.append(
                    ChatSummary(
                        chat_id = c["chat_id"],
                        username = c["username"],
                        display = c["display"],
                        last_msg = c["last_msg"],
                        last_at = c["last_at"],
                    )
                )
            # сортировка по последнему сообщению (DESC)
            chats.sort(key=lambda x: x.last_at, reverse=True)
            self.chatModel.update_chats(chats)
            return

        # Если это сообщение — добавляем его в переписку
        if ptype == "msg":
            # берём серверный ts → переводим в локальное HH:MM
            ts_ms = pkt.get("ts", int(time.time() * 1000))
            dt = datetime.fromtimestamp(ts_ms / 1000, timezone.utc).astimezone()
            time_now = dt.strftime("%H:%M") # Текущее время для отображения

            # Определяем, с кем переписка (если мы получатель, то peer = отправитель, и наоборот)
            peer = pkt["from"] if pkt["from"] != self.username else pkt["to"]
            # Добавляем сообщение в историю переписки с этим пользователем
            self.convs[peer].append((pkt["from"], pkt["text"], time_now))

            # Если сейчас открыт чат с этим пользователем — сразу отображаем сообщение
            if peer == self.recipient:
                self.add_bubble(pkt["from"], pkt["text"], time_now)

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

    # Загружает переписку с выбранным пользователем
    def reload_chat_view(self):
        self.messages.clear()   # Очищаем текущее окно чата
        # Для каждого сообщения в истории текущего собеседника
        for frm, txt, tm in self.convs[self.recipient]:
            self.add_bubble(frm, txt, tm)   # Добавляем пузырёк в интерфейс