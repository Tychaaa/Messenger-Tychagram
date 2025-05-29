from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QPushButton, QMessageBox
)
import requests
from constants import SIGNUP_URL, LOGIN_URL, PASTEL_QSS

class RegisterDialog(QDialog):
    """Окно регистрации нового пользователя (ввод данных и отправка на сервер)."""

    def __init__(self, parent=None):
        """
        Инициализирует диалог регистрации:
        - задаёт заголовок и размер окна;
        - создаёт поля ввода (имя, фамилия, username, пароль);
        - добавляет кнопку регистрации и подключает обработчик;
        - применяет стили оформления.
        """
        super().__init__(parent)
        self.setWindowTitle("Регистрация")
        self.resize(300, 190)

        # Создаём поля ввода данных пользователя
        self.fn = QLineEdit()
        self.fn.setPlaceholderText("Имя")                   # Обязательное поле
        self.ln = QLineEdit()
        self.ln.setPlaceholderText("Фамилия (не обяз.)")    # Необязательное
        self.un = QLineEdit()
        self.un.setPlaceholderText("Username")              # Уникальный логин
        self.pw = QLineEdit()
        self.pw.setPlaceholderText("Пароль")                # Пароль
        self.pw.setEchoMode(QLineEdit.Password)             # Скрываем ввод

        # Кнопка «Создать аккаунт»
        btn = QPushButton("Создать аккаунт")
        btn.setObjectName("sendBtn")  # Применим CSS-стили из темы

        # Компонуем элементы вертикально
        lay = QVBoxLayout(self)
        for w in (self.fn, self.ln, self.un, self.pw, btn):
            lay.addWidget(w)

        # Обработка клика по кнопке — вызываем метод signup()
        btn.clicked.connect(self.signup)

        # Применяем зелёную пастельную тему
        self.setStyleSheet(PASTEL_QSS)

    def signup(self):
        """
        Обрабатывает регистрацию нового пользователя:
        1. Проверяет, что обязательные поля не пустые.
        2. Формирует и отправляет POST-запрос на сервер.
        3. Анализирует ответ сервера и сообщает результат пользователю.
        """
        # 1) Проверка на заполненность обязательных полей
        first_name = self.fn.text().strip()
        username   = self.un.text().strip()
        password   = self.pw.text()

        if not first_name:
            QMessageBox.warning(self, "Пустое поле", "Введите имя")
            return
        if not username:
            QMessageBox.warning(self, "Пустое поле", "Введите имя пользователя")
            return
        if not password:
            QMessageBox.warning(self, "Пустое поле", "Введите пароль")
            return

        # 2) Формируем JSON-объект с данными пользователя
        payload = {
            "username":   username,
            "first_name": first_name,
            "last_name":  self.ln.text().strip(),
            "password":   password
        }
        # Пытаемся отправить POST-запрос на сервер для регистрации
        try:
            r = requests.post(SIGNUP_URL, json=payload, timeout=5)
        except Exception as e:
            # Если возникла ошибка сети — показываем сообщение
            QMessageBox.critical(self, "Ошибка сети", str(e))
            return

        # 3) Обрабатываем ответ сервера
        if r.status_code == 200:
            QMessageBox.information(
                self, "Успех",
                "Регистрация завершена!"
            )
            self.accept()

        # Конфликт: такой username уже занят
        elif r.status_code == 409:
            QMessageBox.warning(
                self, "Имя занято",
                "Пользователь с таким username уже существует."
            )

        # Другая ошибка — выводим код ответа
        else:
            QMessageBox.critical(
                self, "Ошибка регистрации",
                f"Сервер вернул код {r.status_code}"
            )

class LoginDialog(QDialog):
    """Диалог входа с полями Username/Пароль и кнопкой перехода к регистрации."""

    def __init__(self, parent=None):
        """
        Инициализирует окно входа:
        - создаёт поля для ввода имени пользователя и пароля;
        - добавляет кнопки «Войти» и «Регистрация»;
        - подключает обработчики событий;
        - применяет стили оформления.
        """
        super().__init__(parent)
        self.setWindowTitle("Вход")
        self.resize(280, 140)

        # Поля для ввода логина и пароля
        self.un = QLineEdit(); self.un.setPlaceholderText("Username")
        self.pw = QLineEdit(); self.pw.setPlaceholderText("Пароль")
        self.pw.setEchoMode(QLineEdit.Password)

        # Кнопки входа и регистрации
        btnLogin = QPushButton("Войти");
        btnLogin.setObjectName("sendBtn")
        btnReg   = QPushButton("Регистрация");
        btnReg.setObjectName("sendBtn")

        # Размещение всех элементов вертикально
        lay = QVBoxLayout(self)
        for w in (self.un, self.pw, btnLogin, btnReg):
            lay.addWidget(w)

        # Обработка кликов по кнопкам
        btnLogin.clicked.connect(self.login)
        btnReg.clicked.connect(self.open_register)

        # Эти поля будут заполнены при успешном входе
        self.token    = None
        self.username = None

        # Применяем визуальную тему из constants.py
        self.setStyleSheet(PASTEL_QSS)

    def login(self):
        """
        Обрабатывает попытку входа пользователя:
        1. Проверяет, что поля логина и пароля заполнены.
        2. Отправляет POST-запрос на сервер с введёнными данными.
        3. Обрабатывает ответ:
           - при успехе сохраняет токен и имя пользователя, закрывает окно;
           - иначе показывает соответствующее сообщение об ошибке.
        """
        # 1) Проверка: оба поля должны быть заполнены
        username = self.un.text().strip()
        password = self.pw.text()

        if not username:
            QMessageBox.warning(self, "Пустое поле", "Введите имя пользователя")
            return
        if not password:
            QMessageBox.warning(self, "Пустое поле", "Введите пароль")
            return

        # 2) Формируем запрос к серверу
        payload = {"username": username, "password": password}
        try:
            r = requests.post(LOGIN_URL, json=payload, timeout=5)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сети", str(e))
            return

        # 3) Обработка ответа от сервера
        if r.status_code == 200:
            # Успешный вход: сохраняем данные и закрываем окно
            j = r.json()
            self.token    = j["token"]
            self.username = j["username"]
            self.accept()

        elif r.status_code == 404:
            # Пользователь не найден
            QMessageBox.warning(self, "Нет пользователя",
                                "Пользователь не найден.")

        elif r.status_code == 401:
            # Пароль неверный
            QMessageBox.warning(self, "Неверный пароль",
                                "Пароль не совпадает с учётными данными.")

        else:
            # Другая ошибка
            QMessageBox.critical(self, "Ошибка входа",
                                 f"Сервер вернул код {r.status_code}")

    def open_register(self):
        """
        Открывает диалог регистрации.
        После его закрытия (успешного или нет) возвращает пользователя к окну входа.
        """
        reg = RegisterDialog(self)
        reg.exec_()