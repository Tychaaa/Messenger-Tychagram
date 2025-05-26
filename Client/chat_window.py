import time, json
from collections import defaultdict
from datetime import datetime, timezone

from PyQt5.QtCore    import Qt
from PyQt5.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QVBoxLayout, QSplitter
)

from constants import PASTEL_QSS
from ws         import WSBridge
from widgets    import BubbleWidget

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
        self.setStyleSheet(PASTEL_QSS)

        # WebSocket: создаём соединение с сервером
        self.ws_bridge = WSBridge(username)
        self.ws_bridge.got_packet.connect(self.handle_packet)

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

        # Если это пакет со списком пользователей — обновляем список слева
        if ptype == "users":
            self.update_users(pkt["users"])
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