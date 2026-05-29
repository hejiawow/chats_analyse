# -*- coding: utf-8 -*-
"""触发分析 API"""
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.tasks.analysis import run_analysis
from app.services.hujing_api import (
    resolve_user_id_by_name,
    resolve_friend_id_by_phone,
    resolve_friend_by_identifier,
    get_friends_list,
)

router = APIRouter()


class TriggerRequest(BaseModel):
    """统一触发请求，字段可任意组合"""
    user_id: str | None = None
    user_name: str | None = None
    friend_id: int | None = None
    friend_phone: str | None = None
    friend_wx_id: str | None = None
    friend_alias: str | None = None
    user_wx_id: str | None = None
    friend_nick: str | None = None


class TriggerResponse(BaseModel):
    task_id: str
    message: str


def _resolve_ids(req: TriggerRequest) -> tuple[str, int]:
    """
    根据输入信息自动解析 user_id 和 friend_id。

    逻辑：
    1. 有 user_id → 直接用；无则用 user_name 查销售列表匹配
    2. 有 friend_id → 直接用；无则用 friend_phone / friend_wx_id 查好友列表匹配
    """
    # === 解析 user_id ===
    user_id = req.user_id
    if not user_id and req.user_name:
        user_id = resolve_user_id_by_name(req.user_name)
        if not user_id:
            raise HTTPException(status_code=404, detail=f"未找到姓名为「{req.user_name}」的销售")
    if not user_id:
        raise HTTPException(status_code=400, detail="需提供 user_id 或 user_name")

    # === 解析 friend_id ===
    friend_id = req.friend_id
    if not friend_id:
        # 通过手机号匹配
        if req.friend_phone:
            fid, finfo = resolve_friend_id_by_phone(user_id, req.friend_phone)
            if fid:
                friend_id = fid
                if not req.friend_nick:
                    req.friend_nick = finfo.get("nickname") or finfo.get("remark") or req.friend_nick

        # 通过微信号匹配
        if not friend_id and req.friend_wx_id:
            fid, finfo = resolve_friend_by_identifier(user_id, req.friend_wx_id)
            if fid:
                friend_id = fid
                if not req.friend_nick:
                    req.friend_nick = finfo.get("nick") or finfo.get("remark") or req.friend_nick

        # 通过客户别名匹配
        if not friend_id and req.friend_alias:
            fid, finfo = resolve_friend_by_identifier(user_id, req.friend_alias)
            if fid:
                friend_id = fid
                if not req.friend_nick:
                    req.friend_nick = finfo.get("nick") or finfo.get("remark") or req.friend_nick

        if not friend_id:
            detail = "需提供 friend_id，或提供 friend_phone / friend_wx_id / friend_alias 之一"
            raise HTTPException(status_code=404, detail=detail)

    return user_id, friend_id


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_analysis(req: TriggerRequest):
    """
    触发对指定销售-好友聊天记录的分析。

    字段可任意组合：
    - user_id 或 user_name（二选一必填）
    - friend_id / friend_phone / friend_wx_id（三选一必填）
    """
    task_id = str(uuid.uuid4())
    try:
        user_id, friend_id = _resolve_ids(req)

        result = run_analysis.run(
            user_id=user_id,
            friend_id=friend_id,
            user_wx_id=req.user_wx_id,
            friend_wx_id=req.friend_wx_id,
            friend_nick=req.friend_nick,
        )
        return TriggerResponse(
            task_id=task_id,
            message=f"分析完成: {result}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
