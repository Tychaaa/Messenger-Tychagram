from PyQt5.QtWidgets import QApplication
from auth_dialogs import LoginDialog
from chat_window   import ChatWindow
import sys

def main():
    app = QApplication(sys.argv)

    login = LoginDialog()
    if login.exec_() != LoginDialog.Accepted:
        sys.exit()

    win = ChatWindow(login.username, login.token)
    win.show()
    sys.exit(app.exec_())

# Запуск приложения
if __name__ == "__main__":
    main()