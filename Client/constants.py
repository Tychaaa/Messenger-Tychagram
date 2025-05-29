# Адрес WebSocket-соединения, через которое клиент получает и отправляет сообщения
SERVER_URL = "ws://localhost:8080/ws"

# Базовый адрес API-сервера (используется в REST-запросах)
API_BASE   = "http://localhost:8080"

# URL для регистрации нового пользователя (POST)
SIGNUP_URL = f"{API_BASE}/signup"

# URL для входа в систему (POST)
LOGIN_URL  = f"{API_BASE}/login"

# URL для поиска пользователей (GET с параметром q)
USER_SEARCH_URL = f"{API_BASE}/users/search"

# URL для создания личного чата (POST)
CHAT_CREATE_URL = f"{API_BASE}/chats/direct"

# URL для создания группового чата (POST)
GROUP_CREATE_URL = f"{API_BASE}/chats/group"

# Пастельная зелёная тема для виджетов Qt
# Оформляет фон, цвет текста, кнопки, поля ввода и выделения
PASTEL_QSS = """
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

# Стили для QListView в диалогах поиска пользователей
LIST_VIEW_QSS = """
        QListView {
            background-color: #fafafa;     /* светлый фон */
            border: 1px solid #cccccc;     /* тонкая серая рамка */
            border-radius: 8px;            /* скруглённые углы */
            padding: 4px;                  /* внутренний отступ */
        }
        QListView::item {
            border-radius: 4px;            /* скруглённые углы у элемента */
            padding: 6px 8px;              /* отступ внутри элемента */
        }
        QListView::item:selected {
            background-color: #e6f7ff;     /* светло-голубой фон при выделении */
            color: #000000;                /* чёрный текст */
        }
    """

# Стили для списка участников в окне “Новый групповой чат”
GROUP_MEMBER_LIST_QSS = """
        QListView {
            background-color: #fafafa;
            border: 1px solid #cccccc;
            border-radius: 8px;
            padding: 4px;
        }
        QListView::item {
            border-radius: 4px;
        }
        QListView::item:selected {
            background-color: #e6f7ff;
            color: #000000;
        }

        /* Стили для чек-боксов */
        QListView::indicator {
            width: 18px;
            height: 18px;
        }
        QListView::indicator:unchecked {
            border: 2px solid #52b788;
            border-radius: 4px;
            background: white;
        }
        QListView::indicator:checked {
            background-color: #52b788;
            border: 2px solid #52b788;
            border-radius: 4px;
        }
    """