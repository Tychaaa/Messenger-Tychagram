from PyQt5.QtWidgets import QApplication
from auth_dialogs import LoginDialog
from chat_window   import ChatWindow
import sys

def main():
    """
    Точка входа в приложение:
    - запускает интерфейс;
    - показывает окно входа;
    - если вход успешен — открывает основное окно мессенджера.
    """
    app = QApplication(sys.argv)    # Инициализация Qt-приложения

    login = LoginDialog()            # Открываем окно входа
    # Если пользователь закрыл окно или нажал «Отмена» — выходим
    if login.exec_() != LoginDialog.Accepted:
        sys.exit()

    # После успешного входа запускаем окно чата, передаём туда имя пользователя и токен
    win = ChatWindow(login.username, login.token)
    win.show()
    # Запуск главного цикла приложения
    sys.exit(app.exec_())

# Запуск приложения
if __name__ == "__main__":
    main()