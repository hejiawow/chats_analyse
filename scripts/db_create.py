# -*- coding: utf-8 -*-
"""
数据库一键创建脚本

功能：
1. 创建新的 PostgreSQL 数据库
2. 创建所有表结构（与 ORM 模型完全一致）
3. 初始化项目必备数据（用户、角色、关键词）
4. 可选择从原数据库复制数据或全新初始化

使用方式：
    # 全新初始化（新环境部署）
    python scripts/db_create.py --new-db <数据库名> --init-data

    # 从原数据库复制基础数据
    python scripts/db_create.py --new-db <数据库名> --copy-from-source

    # 仅创建表结构（不初始化数据）
    python scripts/db_create.py --new-db <数据库名>

    # 模拟运行
    python scripts/db_create.py --new-db <数据库名> --init-data --dry-run

参数：
    --new-db: 新数据库名称（必需）
    --init-data: 初始化全新默认数据（管理员用户、角色、关键词）
    --copy-from-source: 从原数据库复制基础数据
    --dry-run: 仅打印执行计划，不实际执行
"""
import os
import sys
import json
import argparse
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
if sys.platform == 'win32':
    os.environ['PGCLIENTENCODING'] = 'UTF8'

from sqlalchemy import create_engine, text
from config import settings


# ============================================================
# 默认初始化数据
# ============================================================

# 默认角色
DEFAULT_ROLES = [
    {
        "id": 1,
        "name": "admin",
        "description": "超级管理员，拥有所有权限",
        "permissions": ["admin:all"],
        "created_at": datetime.now(),
    },
    {
        "id": 2,
        "name": "operator",
        "description": "运营人员，可触发分析和查看所有业务结果",
        "permissions": [
            "read:dashboard",
            "read:referral",
            "read:cases",
            "read:journey",
            "read:followup",
            "read:scriptlib",
            "read:rag",
            "read:agents",
            "write:trigger",
        ],
        "created_at": datetime.now(),
    },
    {
        "id": 3,
        "name": "viewer",
        "description": "观察者，只能查看结果，不能触发分析",
        "permissions": [
            "read:dashboard",
            "read:referral",
            "read:cases",
            "read:journey",
            "read:followup",
            "read:scriptlib",
        ],
        "created_at": datetime.now(),
    },
]

# 默认管理员用户（密码: admin123）
# 密码哈希通过 bcrypt 生成，与 app/services/auth.py 中的 hash_password 一致
# 使用: bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
DEFAULT_ADMIN_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.qO.Bo2G0F9K7eK"

DEFAULT_USERS = [
    {
        "id": 1,
        "username": "admin",
        "password_hash": DEFAULT_ADMIN_PASSWORD_HASH,  # 密码: admin123
        "email": "admin@example.com",
        "phone": None,
        "status": "active",
        "last_login": None,
        "created_at": datetime.now(),
    },
]

# 默认用户角色关联
DEFAULT_USER_ROLES = [
    {"user_id": 1, "role_id": 1},  # admin 用户关联 admin 角色
]

# 默认风险关键词（与 keyword_config.py 中 init_default_keywords 一致）
DEFAULT_RISK_KEYWORDS = [
    {"keyword": "退款", "category": "refund", "severity": "high"},
    {"keyword": "退费", "category": "refund", "severity": "high"},
    {"keyword": "退掉", "category": "refund", "severity": "medium"},
    {"keyword": "退钱", "category": "refund", "severity": "medium"},
    {"keyword": "返还", "category": "refund", "severity": "medium"},
    {"keyword": "投诉", "category": "complaint", "severity": "high"},
    {"keyword": "举报", "category": "complaint", "severity": "high"},
    {"keyword": "告你们", "category": "complaint", "severity": "high"},
    {"keyword": "投诉你们", "category": "complaint", "severity": "high"},
    {"keyword": "取消订单", "category": "order_cancel", "severity": "medium"},
    {"keyword": "退订", "category": "order_cancel", "severity": "medium"},
    {"keyword": "不买了", "category": "order_cancel", "severity": "medium"},
    {"keyword": "不想买了", "category": "order_cancel", "severity": "medium"},
    {"keyword": "工商", "category": "regulatory", "severity": "high"},
    {"keyword": "消费者协会", "category": "regulatory", "severity": "high"},
    {"keyword": "消协", "category": "regulatory", "severity": "high"},
    {"keyword": "12315", "category": "regulatory", "severity": "high"},
    {"keyword": "市场监管局", "category": "regulatory", "severity": "high"},
    {"keyword": "骗人", "category": "fraud", "severity": "medium"},
    {"keyword": "骗子", "category": "fraud", "severity": "medium"},
    {"keyword": "欺诈", "category": "fraud", "severity": "high"},
    {"keyword": "虚假宣传", "category": "fraud", "severity": "high"},
    {"keyword": "承诺没兑现", "category": "fraud", "severity": "medium"},
]


# ============================================================
# SQL 语句 - 创建表结构（与 ORM 模型完全一致）
# ============================================================

CREATE_TABLES_SQL = {
    # ========== 基础配置表 ==========

    "users": """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    email VARCHAR(128),
    phone VARCHAR(32),
    status VARCHAR(16) DEFAULT 'active',
    last_login TIMESTAMP,
    created_at TIMESTAMP
);
""",
    "users_comments": """
COMMENT ON TABLE users IS '系统用户表';
COMMENT ON COLUMN users.username IS '用户名';
COMMENT ON COLUMN users.password_hash IS '密码哈希';
COMMENT ON COLUMN users.email IS '邮箱';
COMMENT ON COLUMN users.phone IS '手机号';
COMMENT ON COLUMN users.status IS 'active / disabled';
""",
    "roles": """
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) UNIQUE NOT NULL,
    description VARCHAR(256),
    permissions JSONB,
    created_at TIMESTAMP
);
""",
    "roles_comments": """
COMMENT ON TABLE roles IS '系统角色表';
COMMENT ON COLUMN roles.name IS '角色名称';
COMMENT ON COLUMN roles.description IS '角色描述';
COMMENT ON COLUMN roles.permissions IS '权限列表 JSON';
""",
    "user_roles": """
CREATE TABLE user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
""",
    "user_roles_comments": """
COMMENT ON TABLE user_roles IS '用户-角色关联表';
""",
    "risk_keywords": """
CREATE TABLE risk_keywords (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(64) UNIQUE NOT NULL,
    category VARCHAR(32) NOT NULL,
    severity VARCHAR(16) DEFAULT 'medium',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
""",
    "risk_keywords_comments": """
COMMENT ON TABLE risk_keywords IS '风险关键词配置表';
COMMENT ON COLUMN risk_keywords.keyword IS '关键词';
COMMENT ON COLUMN risk_keywords.category IS '类别：refund/complaint/order_cancel/regulatory/fraud';
COMMENT ON COLUMN risk_keywords.severity IS '严重程度：high/medium/low';
COMMENT ON COLUMN risk_keywords.is_active IS '是否启用';
""",
    # ========== 业务数据表 ==========

    "referral_results": """
CREATE TABLE referral_results (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    user_wx_id VARCHAR(64),
    friend_id BIGINT NOT NULL,
    friend_wx_id VARCHAR(64),
    friend_nick VARCHAR(128),
    status VARCHAR(16) DEFAULT 'success',
    result JSONB NOT NULL,
    error_msg TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""",
    "referral_results_comments": """
COMMENT ON TABLE referral_results IS '转介绍检测结果表';
COMMENT ON COLUMN referral_results.user_id IS '销售ID';
COMMENT ON COLUMN referral_results.user_wx_id IS '销售微信号';
COMMENT ON COLUMN referral_results.friend_id IS '好友ID';
COMMENT ON COLUMN referral_results.friend_wx_id IS '好友微信号';
COMMENT ON COLUMN referral_results.friend_nick IS '好友昵称';
COMMENT ON COLUMN referral_results.status IS 'success / failed';
COMMENT ON COLUMN referral_results.result IS '分析结果';
COMMENT ON COLUMN referral_results.error_msg IS '失败原因';
""",
    "sales_journey_results": """
CREATE TABLE sales_journey_results (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    user_wx_id VARCHAR(64),
    friend_id BIGINT NOT NULL,
    friend_wx_id VARCHAR(64),
    friend_nick VARCHAR(128),
    analysis_result JSONB,
    deal_time VARCHAR(32),
    chat_duration VARCHAR(32),
    message_count INTEGER,
    sales_style VARCHAR(256),
    raw_response TEXT,
    status VARCHAR(16) DEFAULT 'success',
    error_msg TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""",
    "sales_journey_results_comments": """
COMMENT ON TABLE sales_journey_results IS '优秀成交案例提取结果表';
COMMENT ON COLUMN sales_journey_results.user_id IS '销售ID';
COMMENT ON COLUMN sales_journey_results.analysis_result IS '6模块完整分析结果JSON';
COMMENT ON COLUMN sales_journey_results.deal_time IS '成交时间';
COMMENT ON COLUMN sales_journey_results.chat_duration IS '聊天总时长';
COMMENT ON COLUMN sales_journey_results.message_count IS '对话轮次';
COMMENT ON COLUMN sales_journey_results.sales_style IS '销售沟通风格';
""",
    "case_extraction_results": """
CREATE TABLE case_extraction_results (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    user_wx_id VARCHAR(64),
    friend_id BIGINT NOT NULL,
    friend_wx_id VARCHAR(64),
    friend_nick VARCHAR(128),
    script_type VARCHAR(32),
    customer_question TEXT,
    sales_answer TEXT,
    customer_intent VARCHAR(128),
    trigger_customer_state TEXT,
    wake_script TEXT,
    script_objective TEXT,
    target_audience TEXT,
    applicable_scenario VARCHAR(256),
    tags VARCHAR(512),
    business_subject VARCHAR(128),
    compliance_risk TEXT,
    core_design_logic TEXT,
    key_techniques VARCHAR(512),
    pitfall_avoid TEXT,
    customer_profile TEXT,
    raw_response TEXT,
    summary JSONB,
    status VARCHAR(16) DEFAULT 'success',
    error_msg TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""",
    "case_extraction_results_comments": """
COMMENT ON TABLE case_extraction_results IS '优秀话术提取结果表';
COMMENT ON COLUMN case_extraction_results.script_type IS '话术类型：销售话术 / 唤醒话术';
COMMENT ON COLUMN case_extraction_results.customer_question IS '客户问题';
COMMENT ON COLUMN case_extraction_results.sales_answer IS '销冠回答';
COMMENT ON COLUMN case_extraction_results.customer_intent IS '客户意图';
""",
    "follow_up_compliance_results": """
CREATE TABLE follow_up_compliance_results (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    user_wx_id VARCHAR(64),
    friend_id BIGINT NOT NULL,
    friend_wx_id VARCHAR(64),
    friend_nick VARCHAR(128),
    is_compliant VARCHAR(16) NOT NULL,
    total_follow_up_days INTEGER,
    chat_date_range VARCHAR(64),
    window_size_days INTEGER DEFAULT 60,
    min_required_count INTEGER DEFAULT 11,
    min_window_count INTEGER,
    violation_windows JSONB,
    raw_response TEXT,
    status VARCHAR(16) DEFAULT 'success',
    error_msg TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""",
    "follow_up_compliance_results_comments": """
COMMENT ON TABLE follow_up_compliance_results IS '督学跟进合规检测结果表';
COMMENT ON COLUMN follow_up_compliance_results.is_compliant IS 'compliant / non_compliant';
COMMENT ON COLUMN follow_up_compliance_results.total_follow_up_days IS '总跟进天数（去重后）';
COMMENT ON COLUMN follow_up_compliance_results.window_size_days IS '滑动窗口大小（天）';
COMMENT ON COLUMN follow_up_compliance_results.min_required_count IS '窗口内最低跟进次数要求';
""",
    "quality_check_results": """
CREATE TABLE quality_check_results (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    user_name VARCHAR(64),
    user_wx_id VARCHAR(64),
    friend_id BIGINT NOT NULL,
    friend_name VARCHAR(128),
    friend_wx_id VARCHAR(64),
    friend_nick VARCHAR(128),
    check_time_start VARCHAR(32),
    check_time_end VARCHAR(32),
    chat_record_count INTEGER,
    keyword_detected VARCHAR(16) DEFAULT 'no',
    detected_keywords VARCHAR(512),
    keyword_matches JSONB,
    risk_level VARCHAR(16),
    risk_category VARCHAR(64),
    risk_description TEXT,
    suggested_action TEXT,
    key_evidence JSONB,
    raw_response TEXT,
    status VARCHAR(16) DEFAULT 'success',
    error_msg TEXT,
    batch_task_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_quality_check_user_id ON quality_check_results(user_id);
CREATE INDEX IF NOT EXISTS ix_quality_check_risk_level ON quality_check_results(risk_level);
CREATE INDEX IF NOT EXISTS ix_quality_check_created_at ON quality_check_results(created_at);
CREATE INDEX IF NOT EXISTS ix_quality_check_user_created ON quality_check_results(user_id, created_at);
""",
    "quality_check_results_comments": """
COMMENT ON TABLE quality_check_results IS '质检检测结果表';
COMMENT ON COLUMN quality_check_results.keyword_detected IS 'yes/no 是否检测到关键词';
COMMENT ON COLUMN quality_check_results.risk_level IS '风险等级：high/medium/low/none';
COMMENT ON COLUMN quality_check_results.risk_category IS '风险类别：投诉/退款/退费/取消订单等';
""",
    "case_script_library": """
CREATE TABLE case_script_library (
    id SERIAL PRIMARY KEY,
    source_case_id INTEGER,
    user_id VARCHAR(64) NOT NULL,
    user_wx_id VARCHAR(64),
    friend_id BIGINT NOT NULL,
    friend_wx_id VARCHAR(64),
    friend_nick VARCHAR(128),
    scenario_type VARCHAR(128),
    customer_type VARCHAR(64),
    communication_stage VARCHAR(64),
    sales_quote TEXT,
    comprehensive_review TEXT,
    customer_profile TEXT,
    document_text TEXT NOT NULL,
    embedding vector(1024),
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""",
    "case_script_library_comments": """
COMMENT ON TABLE case_script_library IS '话术知识库表';
COMMENT ON COLUMN case_script_library.embedding IS '向量嵌入 (pgvector)';
""",
    "case_script_library_index": """
CREATE INDEX IF NOT EXISTS ix_script_lib_embedding
ON case_script_library
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
""",
}


# ============================================================
# 数据操作函数
# ============================================================

def read_table_data(engine, table_name: str) -> list:
    """从源数据库读取表数据"""
    print(f"  [读取] {table_name}...")
    with engine.connect() as conn:
        # 检查表是否存在
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :name)"
        ), {"name": table_name})
        if not result.scalar():
            print(f"  [警告] {table_name}: 源数据库中不存在，跳过")
            return []

        result = conn.execute(text(f"SELECT * FROM {table_name}"))
        columns = result.keys()
        rows = [dict(zip(columns, row)) for row in result.fetchall()]

        for row in rows:
            for key, value in row.items():
                if isinstance(value, datetime):
                    row[key] = value.isoformat()

        print(f"  [读取] {table_name}: {len(rows)} 条记录")
        return rows


def insert_default_data(engine, table_name: str, data: list):
    """插入默认初始化数据"""
    if not data:
        print(f"  [插入] {table_name}: 无数据，跳过")
        return

    print(f"  [插入] {table_name}: {len(data)} 条记录...")

    with engine.connect() as conn:
        for row in data:
            params = {}
            for key, value in row.items():
                if value is None:
                    params[key] = None
                elif isinstance(value, datetime):
                    params[key] = value.isoformat()
                elif isinstance(value, (dict, list)):
                    params[key] = json.dumps(value)
                else:
                    params[key] = value

            # 构建 INSERT 语句
            columns = list(params.keys())
            columns_str = ", ".join(columns)
            placeholders = ", ".join([f":{col}" for col in columns])

            conn.execute(
                text(f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"),
                params
            )
        conn.commit()

    print(f"  [插入] {table_name}: 完成")


def insert_copied_data(engine, table_name: str, data: list):
    """插入从源数据库复制的数据"""
    if not data:
        print(f"  [插入] {table_name}: 无数据，跳过")
        return

    print(f"  [插入] {table_name}: {len(data)} 条记录...")

    columns = list(data[0].keys())
    columns_str = ", ".join(columns)
    placeholders = ", ".join([f":{col}" for col in columns])

    with engine.connect() as conn:
        for row in data:
            params = {}
            for key, value in row.items():
                if value is None:
                    params[key] = None
                elif isinstance(value, (dict, list)):
                    params[key] = json.dumps(value)
                elif isinstance(value, str) and key in ('permissions', 'result', 'analysis_result',
                                                          'summary', 'violation_windows', 'keyword_matches',
                                                          'key_evidence'):
                    try:
                        json.loads(value)
                        params[key] = value
                    except:
                        params[key] = json.dumps(value)
                else:
                    params[key] = value

            conn.execute(
                text(f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"),
                params
            )
        conn.commit()

    print(f"  [插入] {table_name}: 完成")


def create_table(engine, table_name: str):
    """创建表"""
    print(f"  [创建] {table_name}...")
    sql = CREATE_TABLES_SQL.get(table_name)
    if not sql:
        print(f"  [警告] {table_name}: 未找到建表 SQL")
        return

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()


def create_table_comments(engine, table_name: str):
    """创建表注释"""
    sql = CREATE_TABLES_SQL.get(f"{table_name}_comments")
    if not sql:
        return

    with engine.connect() as conn:
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        for stmt in statements:
            if stmt:
                conn.execute(text(stmt))
        conn.commit()


# ============================================================
# 主流程
# ============================================================

def run_create(new_db_name: str, init_data: bool = False, copy_from_source: bool = False, dry_run: bool = False):
    """执行数据库创建"""
    print("=" * 60)
    print("数据库创建脚本")
    print("=" * 60)

    if not settings.DATABASE_URL_SYNC:
        print("错误: DATABASE_URL_SYNC 未配置，请检查 .env 文件")
        return

    # 解析原数据库连接信息
    original_url = settings.DATABASE_URL_SYNC

    if '@' in original_url and '/' in original_url.split('@')[1]:
        auth_part = original_url.split('@')[0]
        host_port_db = original_url.split('@')[1]
        host_port = host_port_db.rsplit('/', 1)[0]

        postgres_url = f"{auth_part}@{host_port}/postgres"
        new_db_url = f"{auth_part}@{host_port}/{new_db_name}"
    else:
        print("错误: DATABASE_URL_SYNC 格式不正确")
        return

    print(f"原数据库: {host_port_db}")
    print(f"新数据库: {new_db_name}")
    print(f"数据模式: {'初始化默认数据' if init_data else '从源复制' if copy_from_source else '仅创建表结构'}")
    print(f"执行模式: {'模拟运行 (dry-run)' if dry_run else '实际执行'}")
    print("=" * 60)

    # ========== Step 1: 创建新数据库 ==========
    print("\n[Step 1] 创建新数据库...")

    if not dry_run:
        postgres_engine = create_engine(postgres_url, connect_args={'client_encoding': 'utf8'})
        with postgres_engine.connect() as conn:
            # PostgreSQL 创建数据库需要在自动提交模式下执行
            conn.execute(text("COMMIT"))
            result = conn.execute(text(
                "SELECT 1 FROM pg_database WHERE datname = :name"
            ), {"name": new_db_name})

            if result.fetchone():
                print(f"  [警告] 数据库 '{new_db_name}' 已存在，跳过创建")
            else:
                conn.execute(text(f"CREATE DATABASE {new_db_name}"))
                print(f"  [创建] 数据库 '{new_db_name}' 成功")

        postgres_engine.dispose()
    else:
        print(f"  [模拟] CREATE DATABASE {new_db_name};")

    # ========== Step 2: 安装 pgvector 扩展 ==========
    print("\n[Step 2] 安装 pgvector 扩展...")

    if not dry_run:
        new_engine = create_engine(new_db_url, connect_args={'client_encoding': 'utf8'})
        with new_engine.connect() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                print(f"  [安装] pgvector 扩展成功")
            except Exception as e:
                print(f"  [警告] pgvector 扩展安装失败: {e}")
                print(f"  [提示] 如需使用向量功能，请先在 PostgreSQL 安装 pgvector")
    else:
        print(f"  [模拟] CREATE EXTENSION IF NOT EXISTS vector;")

    # ========== Step 3: 创建所有表结构 ==========
    print("\n[Step 3] 创建所有表结构...")

    # 创建顺序（先创建被引用的表）
    create_order = [
        ("users", False),
        ("users_comments", True),
        ("roles", False),
        ("roles_comments", True),
        ("user_roles", False),
        ("user_roles_comments", True),
        ("risk_keywords", False),
        ("risk_keywords_comments", True),
        ("referral_results", False),
        ("referral_results_comments", True),
        ("sales_journey_results", False),
        ("sales_journey_results_comments", True),
        ("case_extraction_results", False),
        ("case_extraction_results_comments", True),
        ("follow_up_compliance_results", False),
        ("follow_up_compliance_results_comments", True),
        ("quality_check_results", False),
        ("quality_check_results_comments", True),
        ("case_script_library", False),
        ("case_script_library_comments", True),
        ("case_script_library_index", True),
    ]

    if not dry_run:
        for table_name, is_comment in create_order:
            if is_comment:
                create_table_comments(new_engine, table_name)
            else:
                create_table(new_engine, table_name)
    else:
        for table_name, is_comment in create_order:
            if not is_comment:
                print(f"  [模拟] CREATE TABLE {table_name};")

    # ========== Step 4: 初始化数据 ==========
    print("\n[Step 4] 初始化数据...")

    if init_data:
        # 全新初始化模式
        print("  [模式] 初始化默认数据")
        if not dry_run:
            insert_default_data(new_engine, "roles", DEFAULT_ROLES)
            insert_default_data(new_engine, "users", DEFAULT_USERS)
            insert_default_data(new_engine, "user_roles", DEFAULT_USER_ROLES)

            # 添加创建时间
            keywords_data = []
            now = datetime.now().isoformat()
            for kw in DEFAULT_RISK_KEYWORDS:
                keywords_data.append({
                    "keyword": kw["keyword"],
                    "category": kw["category"],
                    "severity": kw["severity"],
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                })
            insert_default_data(new_engine, "risk_keywords", keywords_data)
        else:
            print(f"  [模拟] INSERT roles: {len(DEFAULT_ROLES)} 条")
            print(f"  [模拟] INSERT users: {len(DEFAULT_USERS)} 条 (admin / admin123)")
            print(f"  [模拟] INSERT user_roles: {len(DEFAULT_USER_ROLES)} 条")
            print(f"  [模拟] INSERT risk_keywords: {len(DEFAULT_RISK_KEYWORDS)} 条")

    elif copy_from_source:
        # 从原数据库复制模式
        print("  [模式] 从原数据库复制基础数据")
        if not dry_run:
            original_engine = create_engine(original_url, connect_args={'client_encoding': 'utf8'})

            copy_order = ["roles", "users", "user_roles", "risk_keywords"]
            for table_name in copy_order:
                data = read_table_data(original_engine, table_name)
                if data:
                    insert_copied_data(new_engine, table_name, data)

            original_engine.dispose()
        else:
            print("  [模拟] 跳过数据复制步骤")

    else:
        print("  [模式] 仅创建表结构，不初始化数据")

    # ========== 完成 ==========
    if not dry_run:
        new_engine.dispose()

    print("\n" + "=" * 60)
    print("数据库创建完成!")
    print("=" * 60)

    if dry_run:
        print("\n提示: 这是模拟运行，实际执行请去掉 --dry-run 参数")
    else:
        print(f"\n新数据库连接 URL:")
        print(f"  DATABASE_URL_SYNC={new_db_url}")

        if init_data:
            print("\n默认登录信息:")
            print("  用户名: admin")
            print("  密码: admin123")
            print("  ⚠️  请在生产环境中修改默认密码!")

        print("\n表统计:")
        if not dry_run:
            new_engine = create_engine(new_db_url, connect_args={'client_encoding': 'utf8'})
            with new_engine.connect() as conn:
                tables = ["users", "roles", "user_roles", "risk_keywords",
                          "referral_results", "case_extraction_results", "sales_journey_results",
                          "follow_up_compliance_results", "quality_check_results", "case_script_library"]
                for table_name in tables:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                    print(f"  {table_name}: {count} 条记录")
            new_engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="数据库创建脚本 - 创建新数据库，不修改原数据库")
    parser.add_argument("--new-db", required=True, help="新数据库名称")
    parser.add_argument("--init-data", action="store_true", help="初始化全新默认数据（管理员用户、角色、关键词）")
    parser.add_argument("--copy-from-source", action="store_true", help="从原数据库复制基础数据")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际执行")
    args = parser.parse_args()

    # 检查参数冲突
    if args.init_data and args.copy_from_source:
        print("错误: --init-data 和 --copy-from-source 不能同时使用")
        return

    run_create(
        new_db_name=args.new_db,
        init_data=args.init_data,
        copy_from_source=args.copy_from_source,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()