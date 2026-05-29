from typing import Dict, Type, Optional, List

from .base import DataSource
from .hujing import HujingDataSource


class DataSourceManager:
    """数据源管理器 - 采用工厂模式管理所有数据源"""

    _sources: Dict[str, Type[DataSource]] = {}

    @classmethod
    def register(cls, name: str, source_class: Type[DataSource]):
        """注册数据源"""
        cls._sources[name] = source_class

    @classmethod
    def get(cls, name: str) -> Optional[DataSource]:
        """获取数据源实例"""
        source_class = cls._sources.get(name)
        if source_class:
            return source_class()
        return None

    @classmethod
    def list_all(cls) -> List[str]:
        """获取所有已注册的数据源名称"""
        return list(cls._sources.keys())

    @classmethod
    def list_all_with_info(cls) -> List[dict]:
        """获取所有数据源的详细信息（包含显示名称）"""
        result = []
        for name, source_class in cls._sources.items():
            instance = source_class()
            result.append({"name": name, "display_name": instance.get_display_name()})
        return result


# 注册默认数据源
DataSourceManager.register("hujing", HujingDataSource)