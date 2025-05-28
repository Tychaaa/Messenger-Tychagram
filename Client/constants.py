# Адрес сервера, к которому подключается клиент по WebSocket
SERVER_URL = "ws://localhost:8080/ws"

API_BASE   = "http://localhost:8080"
SIGNUP_URL = f"{API_BASE}/signup"
LOGIN_URL  = f"{API_BASE}/login"

# Стилизация пастельно-зелёной темой
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