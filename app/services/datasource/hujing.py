from typing import List, Dict, Tuple, Optional

from .base import DataSource
from app.services.hujing_api import (
    get_chat_records,
    get_all_sales,
    resolve_user_id_by_name,
    resolve_friend_by_identifier,
    get_friends_list,
)


class HujingDataSource(DataSource):
    """虎鲸数据源适配器"""

    def get_name(self) -> str:
        return "hujing"

    def get_display_name(self) -> str:
        return "虎鲸数据"

    def get_chat_records(self, user_id: str, friend_id: int, **kwargs) -> List[dict]:
        return get_chat_records(user_id, friend_id, **kwargs)

    def get_all_sales(self, **kwargs) -> List[dict]:
        return get_all_sales(**kwargs)

    def resolve_user_id_by_name(self, username: str) -> Optional[str]:
        return resolve_user_id_by_name(username)

    def resolve_friend_by_identifier(
        self, user_id: str, identifier: str
    ) -> Tuple[Optional[int], Optional[dict]]:
        return resolve_friend_by_identifier(user_id, identifier)

    def get_friends_list(self, user_id: str, **kwargs) -> List[dict]:
        return get_friends_list(user_id, **kwargs)