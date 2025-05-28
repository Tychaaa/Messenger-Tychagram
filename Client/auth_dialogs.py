# auth_dialogs.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QPushButton, QMessageBox
)
import json, requests
from constants import SIGNUP_URL, LOGIN_URL, PASTEL_QSS


class RegisterDialog(QDialog):
    """Диалог регистрации (Имя, фамилия, username, пароль)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Регистрация")
        self.resize(300, 190)

        # Поля ввода
        self.fn = QLineEdit(); self.fn.setPlaceholderText("Имя")
        self.ln = QLineEdit(); self.ln.setPlaceholderText("Фамилия (не обяз.)")
        self.un = QLineEdit(); self.un.setPlaceholderText("Username")
        self.pw = QLineEdit(); self.pw.setPlaceholderText("Пароль")
        self.pw.setEchoMode(QLineEdit.Password)

        # Кнопка «Создать аккаунт»
        btn = QPushButton("Создать аккаунт")
        btn.setObjectName("sendBtn")  # стилизуем как в чате

        # Компоновка
        lay = QVBoxLayout(self)
        for w in (self.fn, self.ln, self.un, self.pw, btn):
            lay.addWidget(w)
        btn.clicked.connect(self.signup)

        # Применяем тему
        self.setStyleSheet(PASTEL_QSS)

    def signup(self):
        # 1) проверка на пустые поля
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

        # 2) запрос на сервер
        payload = {
            "username":   username,
            "first_name": first_name,
            "last_name":  self.ln.text().strip(),
            "password":   password
        }
        try:
            r = requests.post(SIGNUP_URL, json=payload, timeout=5)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сети", str(e))
            return

        # 3) разбор ответа
        if r.status_code == 200:
            QMessageBox.information(
                self, "Успех",
                "Регистрация завершена!"
            )
            self.accept()

        elif r.status_code == 409:
            QMessageBox.warning(
                self, "Имя занято",
                "Пользователь с таким username уже существует."
            )

        else:
            QMessageBox.critical(
                self, "Ошибка регистрации",
                f"Сервер вернул код {r.status_code}"
            )


class LoginDialog(QDialog):
    """Диалог входа с полями Username/Пароль + кнопка Регистрация."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Вход")
        self.resize(280, 140)

        # Поля ввода
        self.un = QLineEdit(); self.un.setPlaceholderText("Username")
        self.pw = QLineEdit(); self.pw.setPlaceholderText("Пароль")
        self.pw.setEchoMode(QLineEdit.Password)

        # Кнопки
        btnLogin = QPushButton("Войти");      btnLogin.setObjectName("sendBtn")
        btnReg   = QPushButton("Регистрация"); btnReg.setObjectName("sendBtn")

        # Компоновка
        lay = QVBoxLayout(self)
        for w in (self.un, self.pw, btnLogin, btnReg):
            lay.addWidget(w)

        btnLogin.clicked.connect(self.login)
        btnReg.clicked.connect(self.open_register)

        self.token    = None
        self.username = None

        # Применяем тему
        self.setStyleSheet(PASTEL_QSS)

    def login(self):
        # 1) проверка на пустоту
        username = self.un.text().strip()
        password = self.pw.text()

        if not username:
            QMessageBox.warning(self, "Пустое поле", "Введите имя пользователя")
            return
        if not password:
            QMessageBox.warning(self, "Пустое поле", "Введите пароль")
            return

        # 2) запрос на сервер
        payload = {"username": username, "password": password}
        try:
            r = requests.post(LOGIN_URL, json=payload, timeout=5)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сети", str(e))
            return

        # 3) разбор ответа
        if r.status_code == 200:
            j = r.json()
            self.token    = j["token"]
            self.username = j["username"]
            self.accept()

        elif r.status_code == 404:
            QMessageBox.warning(self, "Нет пользователя",
                                "Пользователь не найден.")

        elif r.status_code == 401:
            QMessageBox.warning(self, "Неверный пароль",
                                "Пароль не совпадает с учётными данными.")

        else:
            QMessageBox.critical(self, "Ошибка входа",
                                 f"Сервер вернул код {r.status_code}")

    def open_register(self):
        reg = RegisterDialog(self)
        reg.exec_()  # по закрытии возвращаемся к логину
