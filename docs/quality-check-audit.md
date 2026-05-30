# 质检分析流程审计报告

审计日期：2026-05-30  
核实日期：2026-05-30（逐行阅读源代码核实，原 15 条全部确认属实，新增 6 条）

## 审计范围

质检分析完整流程：API 触发 → Celery 异步任务 → AI Agent 分析 → 结果持久化 → 查询/导出

涉及文件：
- `app/main.py` — 触发接口
- `app/api/quality_check_query.py` — 查询/导出接口
- `app/tasks/analysis.py` — 单条分析 Celery 任务
- `app/tasks/batch_quality.py` — 批量质检 Celery 任务
- `app/agents/quality_check.py` — 质检 Agent
- `app/services/ai_semaphore.py` — AI 并发控制
- `app/services/cache.py` — Redis 缓存
- `app/services/hujing_api.py` — 虎鲸 API 集成
- `app/models/result.py` — 数据模型

---

## 安全问题

### 1. 硬编码 API 密钥和内网 IP [严重]

**位置**: `app/services/hujing_api.py:406-408`

`get_all_chat_messages()` 方法直接硬编码了内网地址和 API Key：

```python
url = "http://192.168.20.217:8006/api/v1/chat/messages"
headers = {"x-api-key": "sgiwogSDF450AXVCSFF"}
```

**核实说明**: `config.py` 已为 `HUJING_CHAT_API_URL` / `HUJING_CHAT_API_KEY` 预留配置槽，且同文件的 `get_chat_pairs()` 已正确使用这两个配置项，只有 `get_all_chat_messages()` 漏用，修复成本极低。

**风险**:
- 凭据泄露：密钥随代码提交到 Git，任何有代码访问权的人都可获取
- 内网拓扑暴露：IP 地址泄露了内部网络结构
- 使用明文 HTTP 而非 HTTPS，存在中间人攻击风险

**修复建议**:
```python
# get_all_chat_messages() 改为：
url = f"{settings.HUJING_CHAT_API_URL}/api/v1/chat/messages"
headers = {"x-api-key": settings.HUJING_CHAT_API_KEY}
```
- 轮换已泄露的 API Key
- 同步清理同函数中的 `print("DEBUG: ...")` 残留日志（见问题 #16）

---

### 2. 触发接口权限模型澄清：不要混淆系统用户 ID 与虎鲸销售 ID [已澄清]

**位置**: `app/main.py:127`、`app/main.py:193`、`app/main.py:275-313`、`app/main.py:323-350`

**澄清说明（2026-05-30）**: 系统登录用户的 `user_id` 与虎鲸接口中的销售 `user_id` 完全不是同一套标识，不能相互替代。批量质检的产品设计就是允许拥有相关系统权限的人指定任意虎鲸销售 `user_id` 发起质检，因此“请求体中的虎鲸 `user_id` 未绑定当前系统用户”不应被直接判定为越权。

以下触发接口仍应通过 `write:trigger` 权限控制谁可以发起任务，但不应把 `current_user["user_id"]` 覆盖到请求中的虎鲸 `user_id`：

- `/api/trigger`（`main.py:127`）
- `/api/trigger/single`（`main.py:193`）
- `/api/trigger/quality-check`（`main.py:275`）
- `/api/trigger/batch-quality-check`（`main.py:323`，`user_id_filter` 字段同理）

```python
# 正确：虎鲸销售 user_id 来自请求体或姓名解析结果
user_id, friend_id = _resolve_ids(req)
```

**禁止的修复方式**:
```python
# 错误：current_user["user_id"] 是系统账号 ID，不是虎鲸销售 ID
req.user_id = str(current_user["user_id"])
```

**建议**:
- 保留 `require_permission("write:trigger")` 作为触发权限边界
- 如需更细粒度控制，新增独立权限（例如 `write:quality_check:any_sales`），不要用系统账号 ID 冒充虎鲸销售 ID
- 如未来要做“只能触发本人虎鲸数据”，需先在系统用户表或 Token 中建立明确的 `hujing_user_id` / `sales_user_id` 映射字段

---

### 3. CORS 配置过于宽松 [高] ⭐ 新增

**位置**: `app/main.py:104-110`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 允许任意来源
    allow_credentials=True,   # 允许携带凭据
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_origins=["*"]` 与 `allow_credentials=True` 同时存在，违反 W3C CORS 规范（浏览器会拒绝此组合），且任意来源均可发起跨域请求，CSRF 防护形同虚设。

**修复建议**:
```python
allow_origins=["https://your-domain.com"],  # 指定实际域名
allow_credentials=True,
```
或通过 `.env` 注入：`ALLOWED_ORIGINS=https://your-domain.com`

---

### 4. 错误信息泄露内部实现 [中]

**位置**: `app/main.py:183、241、272、313`（4 处）

异常处理直接将 `str(e)` 返回给客户端：

```python
raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
```

会泄露内部堆栈信息、数据库错误、外部 API 响应等敏感内容。

**修复建议**:
- 生产环境返回通用错误信息，如 `"分析失败，请稍后重试"`
- 将详细错误信息记录到服务端日志

---

### 5. CSV 导出公式注入风险 [中]

**位置**: `app/api/quality_check_query.py:202-216`

导出 CSV 时未对 `risk_description`、`suggested_action` 等文本字段进行转义。如果 AI 返回的内容以 `=`、`+`、`-`、`@` 开头，Excel 打开时会将其解释为公式。

**修复建议**:
```python
def sanitize_csv_value(val: str) -> str:
    if val and val[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + val
    return val
```

---

### 6. LIKE 通配符注入 [低]

**位置**: `app/api/quality_check_query.py:48、65`（数据查询和 count 查询各一处）

关键词搜索直接拼接：

```python
QualityCheckResult.detected_keywords.ilike(f"%{keyword}%")
```

用户输入 `%` 或 `_` 会被当作 SQL LIKE 通配符，可以模糊匹配到非预期数据。SQLAlchemy 参数化了查询防止 SQL 注入，但 LIKE 语义可被篡改。

**修复建议**:
```python
safe_keyword = keyword.replace("%", "\\%").replace("_", "\\_")
stmt = stmt.where(QualityCheckResult.detected_keywords.ilike(f"%{safe_keyword}%", escape="\\"))
```

---

### 7. 时间解析无异常处理 [低]

**位置**: `app/api/quality_check_query.py:50、52、67、69、181、183`（6 处）

```python
datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
```

无效时间格式会抛出未捕获的 `ValueError`，导致 500 错误和堆栈信息泄露。

**修复建议**:
- 增加 try/except，返回 400 错误和明确的格式提示
- 或在 Pydantic model 中用 `datetime` 类型自动校验

---

## 性能问题

### 8. AI 信号量阻塞 Celery Worker [严重]

**位置**: `app/services/ai_semaphore.py:77`

信号量获取使用 `time.sleep(0.5)` 轮询等待，最长阻塞 300 秒：

```python
while True:
    # ...check rank...
    time.sleep(0.5)  # 阻塞 worker 线程
```

批量质检 500 个子任务时，大量 worker 同时等待信号量，极易耗尽 worker 池，导致所有任务（不仅是质检）排队。

**修复建议**:
- 方案 A：将 AI 调用任务单独放到专用 Celery 队列（`queue='ai'`），限制该队列的 worker 数量，不再需要信号量
- 方案 B：改用异步信号量（配合 `gevent`/`eventlet` worker 池）
- 方案 C：减小超时时间（如 30s），快速失败而非长时间阻塞

---

### 9. Redis `KEYS` 命令阻塞 [高]

**位置**: `app/services/cache.py:71`

```python
keys = client.keys(pattern)
```

`KEYS` 命令是 O(N) 全库扫描，会阻塞 Redis 服务端。当 key 数量大时，所有依赖 Redis 的请求（缓存、信号量、任务日志）都会超时。

**修复建议**:
```python
def cache_clear_pattern(pattern: str) -> int:
    client = get_redis()
    if client is None:
        return 0
    deleted = 0
    try:
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match=pattern, count=100)
            if keys:
                deleted += client.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        pass
    return deleted
```

---

### 10. 查询条件重复构建 [中]

**位置**: `app/api/quality_check_query.py:41-69`（数据/count 查询各一份）、`app/api/quality_check_query.py:171-184`（导出接口第三份拷贝）

WHERE 条件共有 **3 份拷贝**，违反 DRY 原则。新增过滤条件时容易遗漏，导致数据不一致。

**修复建议**:
- 抽取公共的 `_build_filters()` 函数，接收参数返回过滤条件列表
- 三处查询共用同一组过滤条件

---

### 11. 批量保存逐条提交 [中]

**位置**: `app/tasks/batch_quality.py:160-183`（`run_single_batch_check`）、`app/tasks/batch_quality.py:338-361`（`run_single_check_for_matched_pair`）

每个子任务单独开 Session + commit，500 个子任务就是 500 次数据库往返。

**修复建议**:
- 使用 `session.add_all()` + 批量 commit
- 或每 50-100 条 commit 一次，平衡内存和性能

---

### 12. 信号量 Redis 故障时降级为无限制 [中]

**位置**: `app/services/ai_semaphore.py:79-86`

```python
except Exception as e:
    print(f"AI Semaphore Redis error: {e}, allowing call")
    return True  # fail-open：直接放行
```

Redis 宕机 = AI 并发控制完全失效 → 可能瞬间打满 DashScope API 配额，触发限流甚至封号。

**修复建议**:
- 改为 fail-closed：Redis 不可用时拒绝 AI 调用，返回错误
- 或使用本地令牌桶限流器作为降级方案（如 `threading.Semaphore`）
- 至少应有告警通知

---

### 13. 全局销售缓存无过期机制 [中] ⭐ 新增

**位置**: `app/tasks/batch_quality.py:26-34`

```python
_sales_map_cache = None  # 模块级全局变量

def _get_sales_map() -> dict:
    global _sales_map_cache
    if _sales_map_cache is None:
        sales_list = get_all_sales()
        _sales_map_cache = {s.get("user_id"): s.get("username") for s in sales_list}
    # 首次加载后永不刷新
```

Worker 进程启动后，销售列表永久缓存在内存中。新增/删除销售后，批量质检任务写入的 `user_name` 字段将持续使用过期数据，直到进程重启。

**修复建议**: 复用 `hujing_api.get_all_sales()` 已有的 Redis 缓存机制，删除此模块级变量：
```python
def _get_sales_map() -> dict:
    sales_list = get_all_sales()  # 已有 6 小时 Redis 缓存
    return {s.get("user_id"): s.get("username") for s in sales_list if s.get("user_id")}
```

---

### 14. `get_friends_list` 中 createTime 解析无保护 [中] ⭐ 新增

**位置**: `app/services/hujing_api.py:212`

```python
sorted_friends = sorted(
    unique_friends,
    key=lambda x: datetime.strptime(x.get("createTime", ""), "%Y-%m-%d %H:%M:%S")
)
```

若任意好友记录的 `createTime` 缺失（空字符串 `""` 就会触发 `ValueError`），整个好友列表加载失败，进而导致所有依赖好友列表的 API（触发分析、批量质检）全部崩溃。

**修复建议**:
```python
def _safe_parse_time(t: str) -> datetime:
    try:
        return datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return datetime.min

sorted_friends = sorted(unique_friends, key=lambda x: _safe_parse_time(x.get("createTime", "")))
```

---

### 15. 无结果去重 [低]

并发批量子任务或重复触发时，同一 `(user_id, friend_id, time_range)` 可插入多条 `QualityCheckResult`，没有唯一约束保护。

**修复建议**:
- 在 `QualityCheckResult` 表上添加唯一约束：`UNIQUE(user_id, friend_id, check_time_start, check_time_end)`
- 或在插入前先查询是否已存在

---

### 16. stats 缓存失效逻辑不完整 [中] ⭐ 新增

**位置**: `app/api/quality_check_query.py:249-257` vs `app/tasks/batch_quality.py:237`

批量任务完成时调用 `invalidate_quality_check_stats_cache()`（不传 `user_id`），该函数只清除 admin 全量缓存键 `quality_check:stats`，**不清除**各用户的个人缓存（`quality_check:stats:user:{uid}`）。导致批量质检完成后，非 admin 用户看到的统计数据仍是旧值。

**修复建议**:
```python
# on_batch_complete 中：
invalidate_quality_check_stats_cache()
# invalidate 函数中不传 user_id 时，补充清除所有用户缓存：
cache_clear_pattern("quality_check:stats:user:*")
```

---

## 逻辑问题

### 17. 失败记录写入错误表 [中]

**位置**: `app/tasks/analysis.py:424-434`

任务整体失败时，无论当前 agent 是什么，都写入 `ReferralResult` 表：

```python
ref = _save_referral(user_id, ..., "failed", ..., error_msg=str(e))
session.add(ref)
```

质检失败不会记录在 `QualityCheckResult` 表中，查询时无法发现失败记录。

**修复建议**:
- 根据 `agent` 参数决定写入哪张表
- 或统一建立 `TaskErrorLog` 表记录所有任务失败

---

### 18. 批量与单条路径保存逻辑不一致 [中]

- 单条路径（`analysis.py:379-405`）：所有结果都保存，包括 `risk_level="none"` 的
- 批量路径（`batch_quality.py:157`）：只保存 `keyword_detected == "yes"` 的

这导致批量质检后，统计缺少"无风险"记录，无法计算总检测量，统计数据失真。

**修复建议**:
- 统一保存逻辑：批量路径也保存所有结果（`status="no_keyword"` 的记录）
- 或在统计接口中明确标注"仅统计有风险记录"

---

### 19. 分页响应字段错误 [低]

**位置**: `app/api/quality_check_query.py:80`

```python
return {
    "total": total,
    "page": page_size,      # BUG: 应该是 page，写成了 page_size
    "page_size": page_size,
    "data": [r.to_dict() for r in records],
}
```

`page` 字段返回的是每页大小而非当前页码。

**修复建议**:
```python
"page": page,
```

---

### 20. DEBUG 日志残留生产代码 [低] ⭐ 新增

**位置**: `app/services/hujing_api.py:428-438`

```python
print(f"DEBUG: get_all_chat_messages called with start={start_time}, end={end_time}, duration={total_duration}")
print(f"DEBUG: Created segment: {seg_start_str} - {seg_end_str}")
print(f"DEBUG: Total segments: {len(segments)}")
```

包含时间参数的调试日志输出到 stdout，在生产环境会污染日志系统，并潜在泄露业务数据。

**修复建议**: 改用 `logging.debug(...)` 并在生产环境设置 log level 为 INFO。

---

### 21. Redis 客户端模块级初始化无重连机制 [低] ⭐ 新增

**位置**: `app/tasks/analysis.py:19`、`app/tasks/batch_quality.py:17`

```python
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
```

模块级直接创建连接（非懒加载），若 Redis 在 Worker 启动时短暂不可用，导入即失败，所有分析任务无法执行。与 `cache.py` 的懒加载 + 异常捕获模式不一致。

**修复建议**: 封装为懒加载函数，与 `cache.py:get_redis()` 保持统一风格。

---

## 修复优先级汇总

| 优先级 | 问题编号 | 描述 | 是否新增 |
|--------|----------|------|----------|
| P0 立即修复 | #1 | 硬编码 API 密钥和内网 IP | |
| 已澄清 | #2 | 触发接口权限模型：系统用户 ID 与虎鲸销售 ID 不能混用 | |
| P1 尽快修复 | #3 | CORS 配置过于宽松 | ⭐ 新增 |
| P1 尽快修复 | #8 | AI 信号量阻塞 Worker | |
| P1 尽快修复 | #9 | Redis KEYS 命令阻塞 | |
| P1 尽快修复 | #12 | 信号量 fail-open | |
| P2 计划修复 | #4 | 错误信息泄露（4 处）| |
| P2 计划修复 | #5 | CSV 公式注入 | |
| P2 计划修复 | #10 | 查询条件重复（3 份拷贝）| |
| P2 计划修复 | #11 | 批量保存逐条提交 | |
| P2 计划修复 | #13 | 全局销售缓存无过期机制 | ⭐ 新增 |
| P2 计划修复 | #14 | createTime 解析无保护 | ⭐ 新增 |
| P2 计划修复 | #16 | stats 缓存失效不完整 | ⭐ 新增 |
| P2 计划修复 | #17 | 失败记录写入错误表 | |
| P2 计划修复 | #18 | 批量/单条保存逻辑不一致 | |
| P2 计划修复 | #19 | 分页字段错误 | |
| P3 低优先级 | #6 | LIKE 通配符注入 | |
| P3 低优先级 | #7 | 时间解析无异常处理 | |
| P3 低优先级 | #15 | 无结果去重唯一约束 | |
| P3 低优先级 | #20 | DEBUG 日志残留 | ⭐ 新增 |
| P3 低优先级 | #21 | Redis 客户端无重连机制 | ⭐ 新增 |

---

## 🚨 上生产前必须修复的问题

> 以下问题不修复直接上线，会导致**安全事故、功能损坏或生产系统不可用**，属于硬性阻断项。

### 🔴 阻断项（上线前必须完成）

#### [必修-1] 硬编码 API 密钥（对应 #1）

**为什么阻断**: API Key 已明文写入代码，一旦代码库被他人访问，密钥立即泄露。同时 HTTP 明文传输存在中间人风险。

**修复工作量**: 极小（约 5 分钟）

```python
# app/services/hujing_api.py:406-408 改为：
url = f"{settings.HUJING_CHAT_API_URL}/api/v1/chat/messages"
headers = {"x-api-key": settings.HUJING_CHAT_API_KEY}
```

然后在 `.env` 中填入正确的值（`HUJING_CHAT_API_URL` 和 `HUJING_CHAT_API_KEY` 配置槽已存在），并**立即轮换**已泄露的 Key `sgiwogSDF450AXVCSFF`。

---

#### [必修-2] CORS 配置导致凭据跨域（对应 #3）

**为什么阻断**: `allow_origins=["*"]` + `allow_credentials=True` 组合在 W3C 规范下是无效配置，浏览器会拒绝，导致前端所有携带 Cookie 的跨域请求失败。如果前后端不同域，这会让**登录后的所有 API 调用在浏览器端报错**。

**修复工作量**: 极小（1 行）

```python
# app/main.py:106
allow_origins=["https://your-production-domain.com"],
# 或通过环境变量注入：
allow_origins=os.getenv("ALLOWED_ORIGINS", "https://your-domain.com").split(","),
```

---

#### [必修-3] 错误信息泄露内部实现（对应 #4）

**为什么阻断**: 生产环境将数据库连接串、内部路径、第三方 API 报错等敏感信息直接返回给前端用户，是合规审查的直接红线。

**修复工作量**: 极小（统一替换 4 处）

```python
# app/main.py:183, 241, 272, 313 统一改为：
import logging
logger = logging.getLogger(__name__)

# except 块中：
logger.error(f"分析失败: {e}", exc_info=True)
raise HTTPException(status_code=500, detail="分析失败，请稍后重试")
```

---

#### [必修-4] 分页字段 Bug（对应 #19）

**为什么阻断**: 查询接口返回的 `page` 字段实际是 `page_size` 的值，前端无法正确实现分页跳转，功能性错误，上线后用户立即会发现。

**修复工作量**: 极小（1 个字符）

```python
# app/api/quality_check_query.py:80
"page": page,   # 原来错误写的是 page_size
```

---

#### [必修-5] createTime 解析崩溃风险（对应 #14）

**为什么阻断**: 虎鲸 API 返回的好友数据若有任意一条 `createTime` 为空或格式异常，`get_friends_list()` 会整体抛出未捕获异常，导致**所有触发分析的接口全部 500**，系统核心功能不可用。

**修复工作量**: 小（约 10 分钟）

```python
# app/services/hujing_api.py:212 改为：
def _safe_parse_time(t: str) -> datetime:
    try:
        return datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return datetime.min

sorted_friends = sorted(unique_friends, key=lambda x: _safe_parse_time(x.get("createTime", "")))
```

---

### 🟡 强烈建议（上线前完成，否则高负载下会出问题）

| 编号 | 问题 | 风险描述 |
|------|------|----------|
| #12 | 信号量 fail-open | Redis 一旦抖动，AI 并发失控，可能导致 DashScope 封号 |
| #8 | 信号量阻塞 Worker | 批量质检高并发时 Worker 池耗尽，整个 Celery 任务队列卡死 |
| #9 | Redis KEYS 阻塞 | 缓存清理触发全库扫描，Redis 被阻塞时所有依赖缓存的请求超时 |

---

### ✅ 上线前检查清单

```
[ ] 必修-1：hujing_api.py 硬编码改为读取 settings，并轮换泄露 Key
[ ] 必修-2：CORS allow_origins 设置为实际生产域名
[ ] 必修-3：4 处 str(e) 改为通用错误提示 + 服务端日志
[ ] 必修-4：quality_check_query.py:80 的 "page": page_size 改为 "page": page
[ ] 必修-5：hujing_api.py:212 的 strptime 加 try/except 保护
[ ] 防回归：确认触发接口没有把系统用户 ID 覆盖到虎鲸销售 user_id；如需限制范围，先建立显式映射或细粒度权限
```
