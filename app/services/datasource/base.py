from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional


class DataSource(ABC):
    """数据源抽象基类"""

    @abstractmethod
    def get_name(self) -> str:
        """返回数据源名称（唯一标识）"""
        pass

    @abstractmethod
    def get_display_name(self) -> str:
        """返回数据源显示名称（用于前端展示）"""
        pass

    @abstractmethod
    def get_chat_records(self, user_id: str, friend_id: int, **kwargs) -> List[dict]:
        """获取聊天记录"""
        pass

    @abstractmethod
    def get_all_sales(self, **kwargs) -> List[dict]:
        """获取销售列表"""
        pass

    @abstractmethod
    def resolve_user_id_by_name(self, username: str) -> Optional[str]:
        """通过姓名查找user_id"""
        pass

    @abstractmethod
    def resolve_friend_by_identifier(
        self, user_id: str, identifier: str
    ) -> Tuple[Optional[int], Optional[dict]]:
        """通过标识查找好友，返回 (friend_id, friend_info)"""
        pass

    @abstractmethod
    def get_friends_list(self, user_id: str, **kwargs) -> List[dict]:
        """获取好友列表"""
        pass