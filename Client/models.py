from PyQt5.QtCore import Qt, QAbstractListModel, QModelIndex, QVariant

class ChatSummary:
    """
    Представляет краткую информацию об одном чате:
    используется для отображения списка чатов в боковой панели.
    """

    def __init__(
        self,
        chat_id: int,           # Уникальный ID чата
        username: str,          # Username собеседника (для личных чатов)
        display: str,           # Отображаемое имя (например, имя и фамилия или название группы)
        last_msg: str,          # Последнее сообщение в чате
        last_at: int,           # Время последнего сообщения (в миллисекундах Unix-времени)
        is_group: bool = False  # True, если это групповой чат
    ):
        self.chat_id  = chat_id
        self.username = username
        self.display  = display
        self.last_msg = last_msg
        self.last_at  = last_at
        self.is_group = is_group

class ChatListModel(QAbstractListModel):
    """
    Модель для отображения списка чатов в QListView.
    Работает с объектами ChatSummary.
    """

    # Пользовательские роли (определяют, какие данные можно извлекать из модели)
    ChatIDRole    = Qt.UserRole + 1  # ID чата
    UsernameRole  = Qt.UserRole + 2  # username собеседника (если не групповой)
    DisplayRole   = Qt.UserRole + 3  # отображаемое имя (или название группы)
    LastMsgRole   = Qt.UserRole + 4  # последнее сообщение
    LastAtRole    = Qt.UserRole + 5  # время последнего сообщения
    IsGroupRole   = Qt.UserRole + 6  # является ли чат групповым

    def __init__(self, parent=None):
        """
        Инициализация модели. Начинаем с пустого списка чатов.
        """
        super().__init__(parent)
        self._chats = []    # список объектов ChatSummary

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        """
        Возвращает данные для отображения в QListView.
        В зависимости от указанной роли возвращается нужное поле из ChatSummary.
        """
        if not index.isValid():
            # недопустимый индекс → возвращаем "пусто"
            return QVariant()
        chat = self._chats[index.row()] # получаем чат по номеру строки

        # Роль по умолчанию — просто строка с именем и последним сообщением
        if role == Qt.DisplayRole:
            return f"{chat.display} — {chat.last_msg}"

        # Возвращаем нужное поле в зависимости от запрошенной роли
        if role == self.ChatIDRole:
            return chat.chat_id
        if role == self.UsernameRole:
            return chat.username
        if role == self.DisplayRole:
            return chat.display
        if role == self.LastMsgRole:
            return chat.last_msg
        if role == self.LastAtRole:
            return chat.last_at
        if role == self.IsGroupRole:
            return chat.is_group

        return QVariant()   # если роль неизвестна — возвращаем "пусто"

    def rowCount(self, parent=QModelIndex()):
        """
        Возвращает количество строк (т.е. количество чатов).
        """
        return len(self._chats)

    def update_chats(self, chats: list[ChatSummary]):
        """
        Обновляет список чатов в модели:
        - сообщает Qt, что модель будет перезаписана (beginResetModel);
        - заменяет внутренний список на новый;
        - сообщает Qt, что модель обновлена (endResetModel),
          чтобы интерфейс перерисовался.
        """
        self.beginResetModel()
        self._chats = chats
        self.endResetModel()
