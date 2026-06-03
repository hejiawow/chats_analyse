# -*- coding: utf-8 -*-
"""数据模型注册 — 确保 SQLAlchemy 发现所有表"""
from app.models.result import ReferralResult, CaseExtractionResult
from app.models.script_lib import CaseScriptLibrary
from app.models.auth import User, Role, UserRole
from app.models.system_log import SystemLog
