from PyQt5.QtCore import Qt, QAbstractListModel, QModelIndex, QVariant

class ChatSummary:
    def __init__(
        self,
        chat_id: int,
        username: str,
        display: str,
        last_msg: str,
        last_at: int,
        is_group: bool = False
    ):
        self.chat_id  = chat_id
        self.username = username
        self.display  = display
        self.last_msg = last_msg
        self.last_at  = last_at
        self.is_group = is_group

class ChatListModel(QAbstractListModel):
    ChatIDRole    = Qt.UserRole + 1
    UsernameRole  = Qt.UserRole + 2
    DisplayRole   = Qt.UserRole + 3
    LastMsgRole   = Qt.UserRole + 4
    LastAtRole    = Qt.UserRole + 5
    IsGroupRole   = Qt.UserRole + 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chats = []

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        chat = self._chats[index.row()]
        if role == Qt.DisplayRole:
            return f"{chat.display} — {chat.last_msg}"
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
        return QVariant()

    def rowCount(self, parent=QModelIndex()):
        return len(self._chats)

    def roleNames(self):
        return {
            Qt.DisplayRole:    b'display',
            self.ChatIDRole:   b'chat_id',
            self.UsernameRole: b'username',
            self.DisplayRole:  b'display_name',
            self.LastMsgRole:  b'last_msg',
            self.LastAtRole:   b'last_at',
            self.IsGroupRole:  b'is_group',
        }

    def update_chats(self, chats: list[ChatSummary]):
        self.beginResetModel()
        self._chats = chats
        self.endResetModel()
