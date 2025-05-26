import sys
from PyQt5.QtWidgets import QApplication, QInputDialog
from chat_window import ChatWindow

def main():
    app  = QApplication(sys.argv)
    name, ok = QInputDialog.getText(None, "Login", "Ваше имя:")
    if not ok or not name.strip():
        sys.exit()
    win = ChatWindow(name.strip())
    win.show()
    sys.exit(app.exec_())

# Запуск приложения
if __name__ == "__main__":
    main()