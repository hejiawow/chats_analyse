# -*- coding: utf-8 -*-
"""智能体注册中心

新增业务 Agent 只需：
1. 在 agents/ 下新建文件
2. 用 @AgentRegistry.register("名称") 装饰器注册
3. 无需修改任何其他代码
"""
from functools import wraps
from typing import Callable


class AgentRegistry:
    _agents: dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str):
        """注册一个 Agent"""
        def decorator(func: Callable):
            cls._agents[name] = func

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    @classmethod
    def get(cls, name: str) -> Callable | None:
        return cls._agents.get(name)

    @classmethod
    def list_all(cls) -> dict[str, Callable]:
        return dict(cls._agents)

    @classmethod
    def run_all(cls, user_id: str, friend_id: int, chat_records: list, **kwargs) -> dict:
        """执行所有已注册的 Agent"""
        results = {}
        for name, func in cls._agents.items():
            results[name] = func(user_id, friend_id, chat_records, **kwargs)
        return results
