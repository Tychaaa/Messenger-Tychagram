from PyQt5.QtCore    import Qt, QSize
from PyQt5.QtWidgets import QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout

# Виджет одного сообщения (пузырёк)
class BubbleWidget(QWidget):
    def __init__(self, text: str, outgoing: bool, time_str: str):
        super().__init__()

        # Создаём QLabel с текстом сообщения
        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)                                  # перенос строки по ширине
        lbl_text.setTextInteractionFlags(Qt.TextSelectableByMouse)  # разрешаем выделение текста мышкой
        lbl_text.setStyleSheet("padding:0px; margin:0px;")          # убираем отступы вокруг текста

        # Создаём метку с временем сообщения
        lbl_time = QLabel(time_str)
        lbl_time.setStyleSheet("font-size:11px;")               # небольшой шрифт
        lbl_time.setAlignment(Qt.AlignRight | Qt.AlignBottom)   # правый нижний угол

        # Внутренний контейнер — фон пузырька
        bubble = QFrame()
        bubble_lyt = QVBoxLayout(bubble)                        # вертикальное расположение: сначала текст, потом время
        bubble_lyt.setContentsMargins(10, 6, 10, 6)             # внутренние отступы пузыря
        bubble_lyt.setSpacing(4)                                # расстояние между текстом и временем
        bubble_lyt.addWidget(lbl_text)                          # добавляем текст
        bubble_lyt.addWidget(lbl_time, alignment=Qt.AlignRight) # время справа внизу

        # Настраиваем фон и цвет текста в зависимости от направления (отправитель или получатель)
        if outgoing:
            bubble.setStyleSheet(
                "background:#52b788; color:white; border-radius:10px;"      # зелёный пузырёк
            )
        else:
            bubble.setStyleSheet(
                "background:#ffffff; color:#2d6a4f; border-radius:10px;"    # белый пузырёк
            )

        # Выравниваем пузырёк: входящее — слева, исходящее — справа
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        if outgoing:
            root.addStretch()       # отступ слева
            root.addWidget(bubble)  # сам пузырёк справа
        else:
            root.addWidget(bubble)  # сам пузырёк слева
            root.addStretch()       # отступ справа

    def sizeHint(self):
        # Получаем рекомендуемый размер от текущего layout-а
        return self.layout().sizeHint() + QSize(0, 20)