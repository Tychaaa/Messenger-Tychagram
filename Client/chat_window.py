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

class ChatWindow(QWidget):
    """
    Главное окно мессенджера.
    Слева — список чатов, справа — активный чат и поле ввода сообщения.
    """

    def __init__(self, username: str, token: str):
        """
        Инициализирует интерфейс чата:
        - создаёт список чатов и окно сообщений;
        - настраивает отправку сообщений;
        - подключает WebSocket-соединение и обработку входящих данных.
        """
        super().__init__()
        self.username = username          # Имя текущего пользователя
        self.token = token                # Токен авторизации
        self.recipient = ""               # Текущий собеседник (username)
        self.current_chat_id = 0          # ID выбранного чата
        self.is_group = False             # Флаг: групповой ли чат
        self.convs = defaultdict(list)    # История сообщений по chat_id

        # Общие настройки окна
        self.setWindowTitle(f"Tychagram — {username}")
        self.resize(900, 600)

        # === Левая панель: список чатов ===

        # Кнопка «Новый чат»
        self.newChatBtn = QPushButton("Новый чат")
        self.newChatBtn.setObjectName("sendBtn")
        self.newChatBtn.clicked.connect(self.open_new_chat)

        # Кнопка «Новая группа»
        self.newGroupBtn = QPushButton("Новая группа")
        self.newGroupBtn.setObjectName("sendBtn")
        self.newGroupBtn.clicked.connect(self.open_new_group)

        # Список чатов
        self.chatModel = ChatListModel(self)    # модель чатов
        self.chatListView = QListView()
        self.chatListView.setModel(self.chatModel)
        self.chatListView.setItemDelegate(ChatItemDelegate(self.chatListView))  # кастомный внешний вид
        self.chatListView.setSpacing(2)
        self.chatListView.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.chatListView.setStyleSheet("QListView{background:transparent;border:none;}")
        self.chatListView.clicked.connect(self.on_chat_selected)

        # Компоновка левой панели
        leftBox = QWidget()
        leftLay = QVBoxLayout(leftBox)
        leftLay.setContentsMargins(0, 0, 0, 0)
        leftLay.addWidget(self.newChatBtn)
        leftLay.addWidget(self.newGroupBtn)
        leftLay.addWidget(self.chatListView, 1)

        # === Правая панель: сообщения и ввод ===

        # Список сообщений
        self.messages = QListWidget()
        self.messages.setSpacing(4)
        self.messages.setSelectionMode(QListWidget.NoSelection)
        self.messages.setVerticalScrollMode(QListWidget.ScrollPerPixel)

        # Поле ввода текста
        self.input = QLineEdit()
        self.input.setPlaceholderText("Сообщение…")

        # Кнопка отправки
        self.sendBtn = QPushButton("Send")
        self.sendBtn.setObjectName("sendBtn")
        self.sendBtn.setEnabled(False)                  # блокируется, пока не выбран чат
        self.sendBtn.clicked.connect(self.send)
        self.input.returnPressed.connect(self.send)     # отправка по Enter

        # Компоновка поля ввода и кнопки в одну строку
        inputBar = QHBoxLayout()
        inputBar.addWidget(self.input, 1)
        inputBar.addWidget(self.sendBtn)

        # Заголовок над списком сообщений (имя собеседника)
        self.chatLabel = QLabel("Выберите собеседника в списке слева")

        # Компоновка правой панели
        right = QVBoxLayout()
        right.addWidget(self.chatLabel)
        right.addWidget(self.messages, 1)
        right.addLayout(inputBar)
        rightBox = QWidget()
        rightBox.setLayout(right)

        # Делитель между панелями
        splitter = QSplitter()
        splitter.addWidget(leftBox)
        splitter.addWidget(rightBox)
        splitter.setStretchFactor(1, 1)

        # Устанавливаем основной layout окна
        main = QVBoxLayout(self)
        main.addWidget(splitter)

        # Применяем стилизацию
        self.setStyleSheet(PASTEL_QSS)

        # === WebSocket ===

        # Создаём WebSocket-соединение и подписываемся на входящие пакеты
        self.ws_bridge = WSBridge(username, token)
        self.ws_bridge.got_packet.connect(self.handle_packet)

    def open_new_chat(self):
        """
        Открывает диалог создания нового личного чата.
        После закрытия диалога (если пользователь нажал «Начать»),
        список чатов обновится автоматически через WebSocket push от сервера.
        """
        dlg = NewChatDialog(self.token, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            # Обновление списка чатов произойдёт автоматически по сигналу от сервера
            pass

    def open_new_group(self):
        """
        Открывает диалог создания нового группового чата.
        После подтверждения сервер создаст чат и отправит обновлённый список
        участникам через WebSocket (обновление произойдёт автоматически).
        """
        dlg = NewGroupDialog(self.token, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            # Обновление списка чатов придёт от сервера автоматически
            pass

    def on_chat_selected(self, index):
        """
        Обрабатывает выбор чата из списка:
        - сохраняет ID чата и его тип (личный или групповой);
        - устанавливает имя собеседника (только для личных чатов);
        - обновляет заголовок (имя или название группы);
        - активирует поле ввода и перерисовывает историю сообщений.
        """
        cid = self.chatModel.data(index, ChatListModel.ChatIDRole)      # ID выбранного чата
        is_grp = self.chatModel.data(index, ChatListModel.IsGroupRole)  # Тип чата (групповой или нет)
        self.current_chat_id = cid
        self.is_group = bool(is_grp)

        if self.is_group:
            # В группах нет конкретного получателя
            self.recipient = None
        else:
            # Собеседник
            self.recipient = self.chatModel.data(index, ChatListModel.UsernameRole)

        display = self.chatModel.data(index, ChatListModel.DisplayRole)     # Имя/название для заголовка
        self.chatLabel.setText(display)                                     # Обновляем заголовок окна чата
        self.sendBtn.setEnabled(True)                                       # Разблокируем кнопку отправки
        self.reload_chat_view()                                             # Перерисовываем историю сообщений

    def send(self):
        """
        Отправляет сообщение из текстового поля:
        - проверяет, что текст не пустой;
        - формирует пакет в зависимости от типа чата (групповой или личный);
        - отправляет сообщение через WebSocket;
        - очищает поле ввода.
        """
        txt = self.input.text().strip()
        if not txt:
            # Пустые сообщения не отправляем
            return

        # Формируем пакет для группового чата
        if self.is_group:
            payload = {
                "type": "msg",
                "chat_id": self.current_chat_id,
                "text": txt,
            }
        else:
            # Для личного чата нужен получатель
            if not self.recipient:
                return
            payload = {
                "type": "msg",
                "from": self.username,
                "to": self.recipient,
                "text": txt,
            }

        # Отправляем пакет через WebSocket и очищаем поле
        self.ws_bridge.send(payload)
        self.input.clear()

    def handle_packet(self, pkt: dict):
        """
        Обрабатывает входящие пакеты от сервера по WebSocket.
        Поддерживаются три типа пакетов:
        - "history"  — история сообщений чата;
        - "chats"    — список чатов;
        - "msg"      — новое сообщение.
        """
        ptype = pkt.get("type")     # Определяем тип пакета

        # 1. История сообщений чата
        if ptype == "history":
            chat_id = pkt.get("chat_id", 0)
            messages = pkt.get("messages") or []

            # Очищаем текущую историю чата
            self.convs[chat_id] = []

            for row in messages:
                ts = row.get("ts", 0) / 1000
                hhmm = datetime.fromtimestamp(ts, timezone.utc) \
                    .astimezone().strftime("%H:%M")
                sender = row.get("from", "")
                text = row.get("text", "")
                display_name = row.get("sender_display", sender)

                # Сохраняем сообщение как кортеж: (отправитель, текст, время, имя для отображения)
                self.convs[chat_id].append((sender, text, hhmm, display_name))

            # Если история получена для текущего активного чата — обновляем отображение
            if self.current_chat_id == chat_id:
                self.reload_chat_view()
            return

        # 2. Пакет со списком чатов
        if ptype == "chats":
            raw = pkt.get("chats") or []
            unique = {}     # предотвращаем дубликаты по chat_id

            for c in raw:
                cid = c.get("chat_id", 0)
                if cid in unique:
                    continue  # пропускаем повторы

                is_grp = c.get("is_group", False)
                last_at = c.get("last_at", 0)       # время последнего сообщения
                last_msg = c.get("last_msg", "")    # текст последнего сообщения

                if is_grp:
                    user = ""                   # для групп нет конкретного собеседника
                    disp = c.get("title", "")   # название группы
                else:
                    user = c.get("username", "")    # username собеседника
                    disp = c.get("display", "")     # отображаемое имя собеседника

                # Создаём сводку по чату
                summary = ChatSummary(
                    chat_id=cid,
                    username=user,
                    display=disp,
                    last_msg=last_msg,
                    last_at=last_at,
                    is_group=is_grp,
                )
                unique[cid] = summary

            # Сортируем чаты по времени последнего сообщения (сначала новые)
            chats = list(unique.values())
            chats.sort(key=lambda x: x.last_at, reverse=True)

            # Обновляем модель списка чатов
            self.chatModel.update_chats(chats)
            return

        # 3. Пакет с новым сообщением
        if ptype == "msg":
            ts_ms = pkt.get("ts", int(time.time() * 1000))
            hhmm = datetime.fromtimestamp(ts_ms / 1000, timezone.utc) \
                .astimezone().strftime("%H:%M")

            sender = pkt.get("from")
            text = pkt.get("text", "")
            display_name = pkt.get("sender_display", sender)

            # получаем chat_id (0 → личный)
            cid = pkt.get("chat_id", 0)

            if cid:
                # Групповое сообщение
                # Добавляем в историю
                self.convs[cid].append((sender, text, hhmm, display_name))

                # Если открыт именно этот чат — отрисовываем сообщение сразу
                if self.current_chat_id == cid:
                    self.add_bubble(sender, text, hhmm, display_name)
            else:
                # Личное сообщение
                # Определяем peer (собеседника), чтобы найти нужный чат
                peer = sender if sender != self.username else pkt.get("to")

                # Находим chat_id по username собеседника
                cid = 0
                for row in range(self.chatModel.rowCount()):
                    idx = self.chatModel.index(row, 0)
                    if self.chatModel.data(idx, ChatListModel.UsernameRole) == peer:
                        cid = self.chatModel.data(idx, ChatListModel.ChatIDRole)
                        break

                if cid == 0:
                    # если не нашли такой чат — ничего не делаем
                    return

                # Добавляем сообщение в историю
                self.convs[cid].append((sender, text, hhmm))

                # Если это активный чат — отрисовываем сообщение
                if self.current_chat_id == cid:
                    self.add_bubble(sender, text, hhmm)

            return

    def add_bubble(self, sender: str, text: str, time_str: str, display_name: str = None):
        """
        Добавляет сообщение в виде «пузыря» в окно чата:
        - определяет, является ли сообщение исходящим;
        - создаёт виджет BubbleWidget;
        - добавляет его в QListWidget с прокруткой вниз.
        """
        # Определяем, нужно ли рисовать сообщение справа (если оно от текущего пользователя)
        outgoing = (sender == self.username)

        # Создаём виджет пузыря с учётом направления и подписи
        bubble = BubbleWidget(text, outgoing, time_str, display_name)

        # Оборачиваем его в элемент списка
        item = QListWidgetItem()
        self.messages.addItem(item)
        self.messages.setItemWidget(item, bubble)
        item.setSizeHint(bubble.sizeHint())

        # Автоматически прокручиваем вниз, чтобы видеть последнее сообщение
        self.messages.scrollToBottom()

    def add_sender_label(self, display_name: str):
        """
        Добавляет имя отправителя в виде отдельной подписи над сообщением.
        Используется в групповых чатах для отделения сообщений от разных участников.
        """
        item = QListWidgetItem()        # создаём пустой элемент списка
        label = QLabel(display_name)    # создаём виджет с именем

        # Стили: жирный шрифт и небольшой отступ слева
        label.setStyleSheet("font-weight:bold; margin-left:8px;")

        # Добавляем элемент и прикрепляем к нему виджет QLabel
        self.messages.addItem(item)
        self.messages.setItemWidget(item, label)

    def reload_chat_view(self):
        """
        Полностью перерисовывает текущую переписку на экране:
        - очищает список сообщений;
        - добавляет каждый пузырь сообщений заново из истории self.convs;
        - для групповых чатов отображает имя отправителя.
        """
        self.messages.clear()   # Удаляем все виджеты сообщений

        # Получаем список сообщений для текущего активного чата
        msgs = self.convs.get(self.current_chat_id, [])


        for entry in msgs:
            # Если это групповой чат и запись содержит имя отправителя
            if self.is_group and len(entry) == 4:
                frm, txt, tm, display_name = entry
                self.add_bubble(frm, txt, tm, display_name)
            else:
                # Личный чат или display_name отсутствует — просто добавляем пузырь
                frm, txt, tm = entry[:3]
                self.add_bubble(frm, txt, tm)