from datetime import datetime

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore    import Qt, QSize
from PyQt5.QtWidgets import QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout

from models import ChatListModel

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

class ChatItemDelegate(QtWidgets.QStyledItemDelegate):
    _MARGIN   = 6
    _RADIUS   = 6
    _HEIGHT   = 64

    def paint(self, painter, option, index):
        painter.save()

        # фон карточки
        r = option.rect.adjusted(self._MARGIN, self._MARGIN,
                                 -self._MARGIN, -self._MARGIN)
        if option.state & QtWidgets.QStyle.State_Selected:
            bg = QtGui.QColor("#d0e8ff")
        elif option.state & QtWidgets.QStyle.State_MouseOver:
            bg = QtGui.QColor("#eef5ff")
        else:
            bg = QtGui.QColor("#f7f7f7")
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(r, self._RADIUS, self._RADIUS)

        # данные
        display = index.data(ChatListModel.DisplayRole)
        lastmsg = index.data(ChatListModel.LastMsgRole) or ""
        last_at = index.data(ChatListModel.LastAtRole) or 0

        # прямоугольник для текстов
        inner = r.adjusted(10, 8, -10, -8)

        # 1) Имя слева, время справа
        # — имя
        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#000000"))
        fm_name = QtGui.QFontMetrics(font)
        name_h = fm_name.height()
        painter.drawText(inner.x(), inner.y(),
                         inner.width(), name_h,
                         QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter,
                         display)

        # — время
        ts = datetime.fromtimestamp(last_at/1000)
        timestr = ts.strftime("%H:%M")
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#888888"))
        painter.drawText(inner.x(), inner.y(),
                         inner.width(), name_h,
                         QtCore.Qt.AlignRight|QtCore.Qt.AlignVCenter,
                         timestr)

        # 2) Сообщение под именем
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#444444"))
        fm_msg = QtGui.QFontMetrics(font)
        # обрезаем, если не влезает
        msg = fm_msg.elidedText(lastmsg, QtCore.Qt.ElideRight, inner.width())
        painter.drawText(inner.x(),
                         inner.y() + name_h + 4,
                         inner.width(),
                         fm_msg.height(),
                         QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter,
                         msg)

        painter.restore()

    def sizeHint(self, option, index):
        return QtCore.QSize(option.rect.width(), self._HEIGHT) + QSize(0, 5)