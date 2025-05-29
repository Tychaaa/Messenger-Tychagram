from datetime import datetime

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore    import Qt, QSize
from PyQt5.QtWidgets import QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout

from models import ChatListModel

class BubbleWidget(QWidget):
    """
    Виджет одного сообщения в чате в виде «пузыря».
    Показывает текст, имя отправителя (для групп), время отправки.
    """

    def __init__(
        self,
        text: str,                  # Текст сообщения
        outgoing: bool,             # True, если это исходящее сообщение
        time_str: str,              # Время отправки (формат HH:MM)
        display_name: str = None    # Имя отправителя (для групповых чатов)
    ):
        super().__init__()

        # 1) Имя отправителя (только для групповых чатов)
        if display_name:
            lbl_name = QLabel(display_name)
            name_font = lbl_name.font()
            name_font.setBold(True)
            lbl_name.setFont(name_font)
            lbl_name.setStyleSheet("margin:0; padding:0;")
        else:
            # В личных чатах имя не показывается
            lbl_name = None

        # 2) Текст сообщения
        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)
        lbl_text.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        lbl_text.setStyleSheet("padding:0; margin:0;")

        # 3) Метка с временем отправки
        lbl_time = QLabel(time_str)
        lbl_time.setStyleSheet("font-size:11px;")
        lbl_time.setAlignment(Qt.AlignRight | Qt.AlignBottom)

        # 4) Собираем пузырь: вертикально — имя, текст, время
        bubble = QFrame()
        bubble_lyt = QVBoxLayout(bubble)
        bubble_lyt.setContentsMargins(10, 6, 10, 6)
        bubble_lyt.setSpacing(4)

        if lbl_name:
            bubble_lyt.addWidget(lbl_name)                      # имя отправителя сверху
        bubble_lyt.addWidget(lbl_text)                          # затем текст
        bubble_lyt.addWidget(lbl_time, alignment=Qt.AlignRight) # время внизу

        # 5) Стилизация пузыря: цвет и скругления
        if outgoing:
            # зелёный (исходящее)
            bubble.setStyleSheet(
                "background:#52b788; color:white; border-radius:10px;"
            )
        else:
            # белый (входящее)
            bubble.setStyleSheet(
                "background:#ffffff; color:#2d6a4f; border-radius:10px;"
            )

        # 6) Выравнивание всего пузыря по левому или правому краю
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        if outgoing:
            root.addStretch()       # отступ слева
            root.addWidget(bubble)  # пузырь справа
        else:
            root.addWidget(bubble)  # пузырь слева
            root.addStretch()       # отступ справа

    def sizeHint(self):
        """
        Возвращает рекомендуемый размер пузыря для правильной отрисовки в списке сообщений.
        Учитывает размер внутреннего содержимого + небольшой вертикальный отступ.
        """
        return self.layout().sizeHint() + QSize(0, 20)

class ChatItemDelegate(QtWidgets.QStyledItemDelegate):
    """
    Кастомный делегат для рисования элементов списка чатов.
    Используется в QListView, чтобы каждый элемент выглядел как «карточка» чата.
    """

    _MARGIN = 6   # Отступ от краёв карточки
    _RADIUS = 6   # Радиус скругления углов
    _HEIGHT = 64  # Рекомендуемая высота элемента

    def paint(self, painter, option, index):
        """
        Отрисовывает один элемент списка:
        - фон с разными цветами для выделенного и обычного состояния;
        - имя собеседника/группы слева, время справа;
        - последнее сообщение снизу.
        """
        painter.save()  # сохраняем текущее состояние кисти

        # Фон карточки
        r = option.rect.adjusted(self._MARGIN, self._MARGIN,
                                 -self._MARGIN, -self._MARGIN)

        # Выбор цвета фона в зависимости от состояния
        if option.state & QtWidgets.QStyle.State_Selected:
            # голубой при выделении
            bg = QtGui.QColor("#d0e8ff")
        elif option.state & QtWidgets.QStyle.State_MouseOver:
            # светло-голубой при наведении
            bg = QtGui.QColor("#eef5ff")
        else:
            # серо-белый фон по умолчанию
            bg = QtGui.QColor("#f7f7f7")

        # Рисуем скруглённый прямоугольник
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(r, self._RADIUS, self._RADIUS)

        # Извлекаем данные из модели
        display = index.data(ChatListModel.DisplayRole)         # имя или название группы
        lastmsg = index.data(ChatListModel.LastMsgRole) or ""   # последнее сообщение
        last_at = index.data(ChatListModel.LastAtRole) or 0     # время в миллисекундах

        # Область для текста внутри карточки
        inner = r.adjusted(10, 8, -10, -8)

        # Строка 1: Имя и время
        # Имя собеседника (слева)
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

        # Время (справа)
        if last_at > 0:
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

        # Строка 2: Последнее сообщение
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

        painter.restore()   # восстанавливаем состояние кисти

    def sizeHint(self, option, index):
        """
        Возвращает рекомендуемый размер для одного элемента списка чатов.
        Высота фиксированная (_HEIGHT), ширина зависит от размера виджета.
        Добавляется небольшой вертикальный отступ (5 пикселей).
        """
        return QtCore.QSize(option.rect.width(), self._HEIGHT) + QSize(0, 5)