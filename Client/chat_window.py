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
from new_group_dialog import NewGroupDialog
from ws         import WSBridge
from widgets    import BubbleWidget, ChatItemDelegate


# Главное окно мессенджера
class ChatWindow(QWidget):
    def __init__(self, username: str, token: str):
        super().__init__()
        self.username = username                      # Имя текущего пользователя
        self.token = token
        self.recipient = ""                           # Имя собеседника
        self.current_chat_id = 0
        self.is_group = False
        self.convs = defaultdict(list)                # История переписок: получатель → список сообщений

        # Настройка окна
        self.setWindowTitle(f"Tychagram — {username}")
        self.resize(900, 600)

        # Список пользователей слева
        self.newChatBtn = QPushButton("Новый чат")
        self.newChatBtn.setObjectName("sendBtn")
        self.newChatBtn.clicked.connect(self.open_new_chat)
        self.newGroupBtn = QPushButton("Новая группа")
        self.newGroupBtn.setObjectName("sendBtn")
        self.newGroupBtn.clicked.connect(self.open_new_group)

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
        leftLay.addWidget(self.newGroupBtn)
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

    def open_new_group(self):
        dlg = NewGroupDialog(self.token, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            # после успешного создания на сервере всем придёт обновлённый список чатов
            pass

    # Вызывается при выборе пользователя в списке.
    # Обновляет заголовок чата, активирует поле ввода и загружает историю переписки.
    def on_chat_selected(self, index):
        cid = self.chatModel.data(index, ChatListModel.ChatIDRole)
        is_grp = self.chatModel.data(index, ChatListModel.IsGroupRole)
        self.current_chat_id = cid
        self.is_group = bool(is_grp)

        if self.is_group:
            self.recipient = None
        else:
            self.recipient = self.chatModel.data(index, ChatListModel.UsernameRole)

        display = self.chatModel.data(index, ChatListModel.DisplayRole)
        self.chatLabel.setText(display)
        self.sendBtn.setEnabled(True)
        self.reload_chat_view()

    # Отправляет сообщение выбранному собеседнику через WebSocket
    def send(self):
        txt = self.input.text().strip()
        if not txt:
            return

        if self.is_group:
            payload = {
                "type": "msg",
                "chat_id": self.current_chat_id,
                "text": txt,
            }
        else:
            if not self.recipient:
                return
            payload = {
                "type": "msg",
                "from": self.username,
                "to": self.recipient,
                "text": txt,
            }

        self.ws_bridge.send(payload)
        self.input.clear()

    # Обработка входящих/исходящих пакетов
    def handle_packet(self, pkt: dict):
        ptype = pkt.get("type") # Определяем тип пакета

        if ptype == "history":
            # всегда приходит chat_id и messages
            chat_id = pkt.get("chat_id", 0)
            messages = pkt.get("messages") or []

            # 1) сбрасываем накопленные сообщения для этого чата
            self.convs[chat_id] = []

            # 2) наполняем из пришедшего списка
            for row in messages:
                ts = row.get("ts", 0) / 1000
                hhmm = datetime.fromtimestamp(ts, timezone.utc).astimezone().strftime("%H:%M")
                sender = row.get("from")
                text = row.get("text", "")
                self.convs[chat_id].append((sender, text, hhmm))

            # 3) если сейчас открыт именно этот чат — перерисовываем
            if self.current_chat_id == chat_id:
                self.reload_chat_view()
            return

        # Если это пакет со списком пользователей — обновляем список слева
        if ptype == "chats":
            raw = pkt.get("chats") or []
            unique = {}
            for c in raw:
                cid = c.get("chat_id", 0)
                if cid in unique:
                    continue  # пропускаем дубли
                is_grp = c.get("is_group", False)
                last_at = c.get("last_at", 0)
                last_msg = c.get("last_msg", "")
                if is_grp:
                    user = ""  # в группах нет peer-username
                    disp = c.get("title", "")
                else:
                    user = c.get("username", "")
                    disp = c.get("display", "")
                summary = ChatSummary(
                    chat_id=cid,
                    username=user,
                    display=disp,
                    last_msg=last_msg,
                    last_at=last_at,
                    is_group=is_grp,
                )
                unique[cid] = summary

            chats = list(unique.values())
            chats.sort(key=lambda x: x.last_at, reverse=True)
            self.chatModel.update_chats(chats)
            return

        # Если это сообщение — добавляем его в переписку
        if ptype == "msg":
            # время
            ts_ms = pkt.get("ts", int(time.time() * 1000))
            hhmm = datetime.fromtimestamp(ts_ms / 1000, timezone.utc) \
                .astimezone().strftime("%H:%M")

            # сначала пробуем взять chat_id из пакета (групповые сообщения)
            cid = pkt.get("chat_id", 0)
            if cid == 0:
                # личное сообщение — вычисляем peer
                peer = pkt.get("from") if pkt.get("from") != self.username else pkt.get("to")
                # ищем chat_id в модели
                cid = 0
                for row in range(self.chatModel.rowCount()):
                    idx = self.chatModel.index(row, 0)
                    if self.chatModel.data(idx, ChatListModel.UsernameRole) == peer:
                        cid = self.chatModel.data(idx, ChatListModel.ChatIDRole)
                        break
                # если всё-таки не нашли — выходим
                if cid == 0:
                    return

            # сохраняем сообщение всегда по cid
            self.convs[cid].append((pkt.get("from"), pkt.get("text"), hhmm))
            # показываем в UI, если открыт именно этот чат
            if self.current_chat_id == cid:
                self.add_bubble(pkt.get("from"), pkt.get("text"), hhmm)
            return

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

    def add_sender_label(self, display_name: str):
        """Добавляет над пузырьком label с именем отправителя."""
        item = QListWidgetItem()
        label = QLabel(display_name)
        label.setStyleSheet("font-weight:bold; margin-left:8px;")
        self.messages.addItem(item)
        self.messages.setItemWidget(item, label)

    # Загружает переписку с выбранным пользователем
    def reload_chat_view(self):
        self.messages.clear()
        msgs = self.convs.get(self.current_chat_id, [])
        for frm, txt, tm in msgs:
            self.add_bubble(frm, txt, tm)