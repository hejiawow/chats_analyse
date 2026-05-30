# -*- coding: utf-8 -*-
"""日志查询 API — 查询系统日志、统计、清理"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from app.services.dependencies import require_permission, require_auth, get_current_user
from app.services.system_log_service import log_service

router = APIRouter()


@router.get("/logs")
async def query_logs(
    log_type: Optional[str] = Query(None, description="日志类型: api_access / audit / error"),
    log_level: Optional[str] = Query(None, description="日志级别: debug / info / warning / error / critical"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    username: Optional[str] = Query(None, description="用户名 (模糊匹配)"),
    action: Optional[str] = Query(None, description="操作类型"),
    resource_type: Optional[str] = Query(None, description="资源类型"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    current_user: dict = Depends(require_permission("admin:logs")),
):
    """查询系统日志 (需要 admin:logs 权限)"""
    # 解析时间
    start_dt = None
    end_dt = None
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_time 格式无效")
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_time 格式无效")

    logs, total = await log_service.query_logs(
        log_type=log_type,
        log_level=log_level,
        user_id=user_id,
        username=username,
        action=action,
        resource_type=resource_type,
        start_time=start_dt,
        end_time=end_dt,
        page=page,
        page_size=page_size,
    )

    return {
        "data": [log.to_dict() for log in logs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/logs/statistics")
async def get_log_statistics(
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)"),
    group_by: str = Query("log_type", description="分组维度: log_type / log_level / user_id / action"),
    current_user: dict = Depends(require_permission("admin:logs")),
):
    """获取日志统计 (需要 admin:logs 权限)"""
    start_dt = None
    end_dt = None
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_time 格式无效")
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_time 格式无效")

    stats = await log_service.get_log_statistics(
        start_time=start_dt,
        end_time=end_dt,
        group_by=group_by,
    )

    return {"data": stats}


@router.get("/logs/my-actions")
async def get_my_action_logs(
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    current_user: dict = Depends(require_auth),
):
    """查询当前用户的操作日志 (普通用户可访问)"""
    start_dt = None
    end_dt = None
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_time 格式无效")
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_time 格式无效")

    logs, total = await log_service.query_logs(
        log_type="audit",
        user_id=current_user["user_id"],
        start_time=start_dt,
        end_time=end_dt,
        page=page,
        page_size=page_size,
    )

    return {
        "data": [log.to_dict() for log in logs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.delete("/logs/old")
async def delete_old_logs(
    days: int = Query(90, ge=1, le=365, description="保留最近N天的日志"),
    current_user: dict = Depends(require_permission("admin:logs")),
):
    """清理旧日志 (需要 admin:logs 权限)"""
    deleted_count = await log_service.delete_old_logs(days=days)
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "message": f"已删除 {days} 天前的 {deleted_count} 条日志",
    }