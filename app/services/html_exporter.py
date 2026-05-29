# -*- coding: utf-8 -*-
"""优秀成交案例 HTML 报告生成器 — 固定导出到桌面路径"""
import os
import json
from typing import Optional
from app.services.hujing_api import get_chat_records


# ============================================================
# 固定导出路径（Windows 桌面）
# ============================================================
DEFAULT_EXPORT_PATH = "C:/Users/23824/Desktop"


def generate_html_report(
    analysis_result: dict,
    chat_records: list,
    friend_nick: str = "",
    export_path: Optional[str] = None,
    return_only: bool = False,
) -> str:
    """
    生成并导出优秀成交案例 HTML 复盘报告。

    Args:
        analysis_result: Agent 返回的 6 模块结构化分析结果
        chat_records: 原始聊天记录数组
        friend_nick: 好友昵称/班级名
        export_path: 导出路径，默认使用桌面固定路径
        return_only: 如果为 True，只返回 HTML 内容，不保存文件

    Returns:
        导出文件的绝对路径，或 HTML 内容字符串
    """
    # 构建数据
    basic = analysis_result.get("module1_basic", {})
    journey = analysis_result.get("module2_journey", [])
    scripts = analysis_result.get("module3_scripts", [])
    psychology = analysis_result.get("module4_psychology", [])
    key_factors = analysis_result.get("module5_key_factors", {})
    improvements = analysis_result.get("module6_improvements", {})
    user_profile = basic.get("user_profile", {})

    # 构建聊天数据 JSON
    chat_data = _format_chat_data(chat_records)

    # 渲染 HTML
    html_content = _render_html(
        friend_nick=friend_nick or "成交案例",
        basic=basic,
        journey=journey,
        scripts=scripts,
        psychology=psychology,
        key_factors=key_factors,
        improvements=improvements,
        user_profile=user_profile,
        chat_data=chat_data,
    )

    # 如果只需要返回 HTML 内容，不保存文件
    if return_only:
        return html_content

    # 否则保存文件
    if export_path is None:
        export_path = DEFAULT_EXPORT_PATH

    # 如果导出路径是目录（没有.html后缀），自动拼接文件名
    if not export_path.endswith(".html"):
        export_path = os.path.join(export_path, "玉娆高级职称王者班.html")

    # 确保目录存在
    os.makedirs(os.path.dirname(export_path), exist_ok=True)

    # 写入文件
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return export_path


def _format_chat_data(chat_records: list) -> list:
    """格式化聊天记录为 HTML 可用格式"""
    data = []
    for rec in chat_records:
        data.append({
            "author": rec.get("author", "left"),
            "createTime": rec.get("createTime", ""),
            "headimg": rec.get("headimg", ""),
            "nickName": rec.get("nickName", ""),
            "sentence": rec.get("sentence", ""),
            "type": str(rec.get("type", "1")),
        })
    return data


def _render_html(**ctx) -> str:
    """渲染完整 HTML 报告"""
    from datetime import datetime

    title = f"{ctx['friend_nick']}-成交优秀案例复盘"

    # 基础信息
    basic = ctx['basic']
    deal_time = _esc(basic.get("deal_time", "-"))
    chat_duration = _esc(basic.get("chat_duration", "-"))
    msg_count = basic.get("message_count", 0) or len(ctx.get('chat_data', []))
    sales_style = _esc(basic.get("sales_style", "-"))

    # 用户画像
    up = ctx['user_profile']
    identity = _esc(up.get("identity", "-"))
    concerns = _esc(up.get("concerns", "-"))
    needs = _esc(up.get("needs", "-"))
    pain_points = _esc(up.get("pain_points", "-"))

    # ===== 模块2：流程拆解 HTML（时间线样式） =====
    journey_html = ""
    stage_colors = ['#3b82f6','#6366f1','#8b5cf6','#a855f7','#ec4899','#f43f5e','#ef4444']
    stage_icons = {
        "开场破冰": "👋", "需求挖掘": "🔍", "痛点放大": "⚡",
        "产品价值塑造": "💎", "异议处理": "️", "逼单锁单": "",
        "最终成交": "✅", "开场": "👋", "成交": "✅",
    }
    journey_html += '<div style="position:relative;padding-left:32px;">'
    journey_html += '<div style="position:absolute;left:15px;top:8px;bottom:8px;width:2px;background:linear-gradient(to bottom,#3b82f6,#8b5cf6,#ec4899,#ef4444);border-radius:1px;"></div>'
    for idx, stage in enumerate(ctx['journey']):
        icon = "📌"
        for key, val in stage_icons.items():
            if key in stage.get("stage", ""):
                icon = val
                break
        eff = stage.get("effectiveness", 0) or 0
        score_color = "#22c55e" if eff >= 4 else ("#f59e0b" if eff >= 3 else "#ef4444")
        dot_color = stage_colors[idx % len(stage_colors)]
        journey_html += f"""
            <div style="position:relative;margin-bottom:20px;">
                <div style="position:absolute;left:-32px;top:4px;width:12px;height:12px;border-radius:50%;background:{dot_color};border:3px solid #fff;box-shadow:0 0 0 2px {dot_color};"></div>
                <div style="background:#f8fafc;border-radius:10px;padding:14px;border:1px solid #e2e8f0;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                        <span style="font-weight:700;font-size:15px;color:{dot_color};">{icon} {_esc(stage.get('stage', '未知阶段'))}</span>
                        <span style="font-size:12px;color:#94a3b8;background:#f1f5f9;padding:2px 8px;border-radius:4px;">{_esc(stage.get('time_range', ''))}</span>
                    </div>
                    <div style="font-size:13px;line-height:1.7;">
                        <p style="margin-bottom:6px;"><b style="color:#475569;">销售动作：</b><span style="color:#334155;">{_esc(stage.get('sales_action', ''))}</span></p>
                        <p><b style="color:#475569;">用户反应：</b><span style="color:#334155;">{_esc(stage.get('user_reaction', ''))}</span></p>
                    </div>
                    <div style="margin-top:10px;display:flex;align-items:center;gap:6px;">
                        <span style="font-size:12px;color:#64748b;">效果评分</span>
                        <div style="display:flex;gap:2px;">
                            {''.join(f'<div style="width:16px;height:6px;border-radius:3px;background:{score_color if i < eff else "#e2e8f0"};"></div>' for i in range(5))}
                        </div>
                        <span style="font-size:12px;color:{score_color};font-weight:600;">{eff}/5</span>
                    </div>
                </div>
            </div>"""
    journey_html += '</div>'

    # ===== 模块3：优秀话术 HTML（RAG结构化条目，兼容旧数据） =====
    scripts_html = ""
    for s in ctx['scripts']:
        # 兼容新旧数据结构
        customer_question = _esc(s.get('customer_question', ''))
        sales_answer = _esc(s.get('sales_answer', '') or s.get('quote', ''))
        scene_tag = _esc(s.get('scene_tag', ''))
        customer_intent = _esc(s.get('customer_intent', ''))
        tags = _esc(s.get('tags', ''))
        business_subject = _esc(s.get('business_subject', ''))
        compliance_risk = _esc(s.get('compliance_risk', ''))
        why_good = _esc(s.get('why_good', ''))
        customer_profile = _esc(s.get('customer_profile', ''))
        anti_pitfall = _esc(s.get('anti_pitfall', '') or s.get('reusable_tip', ''))

        tags_html = ""
        if tags:
            tags_html = " ".join([f'<span class="mini-tag">{_esc(t.strip())}</span>' for t in tags.split(',') if t.strip()])

        scripts_html += f"""
            <div class="highlight-card">
                <div class="highlight-header">
                    <div class="highlight-tag">{scene_tag}</div>
                    {f'<div class="highlight-subject">{business_subject}</div>' if business_subject else ''}
                </div>
                <div class="highlight-dialog">
                    {f'<div class="highlight-customer-q"><b>客户：</b>{customer_question}</div>' if customer_question else ''}
                    <div class="highlight-sales-a"><b>销冠：</b>{sales_answer}</div>
                </div>
                <div class="highlight-meta">
                    {f'<div class="meta-row"><b>客户意图：</b>{customer_intent}</div>' if customer_intent else ''}
                    {f'<div class="meta-row"><b>客户画像：</b>{customer_profile}</div>' if customer_profile else ''}
                    {f'<div class="meta-row"><b>标签：</b>{tags_html}</div>' if tags_html else ''}
                    {f'<div class="meta-row"><b>合规风险：</b><span class="risk-text">{compliance_risk}</span></div>' if compliance_risk else ''}
                </div>
                <div class="highlight-analysis">
                    {f'<p><b>话术拆解分析：</b>{why_good}</p>' if why_good else ''}
                    {f'<p><b>反例避坑：</b><span class="anti-pitfall">{anti_pitfall}</span></p>' if anti_pitfall else ''}
                </div>
            </div>"""

    # ===== 模块4：心理变化曲线 HTML =====
    psych_html = ""
    psych_states = {
        "陌生": ("#94a3b8", "🧊"), "防备": ("#f59e0b", "🛡️"),
        "观望": ("#3b82f6", "👀"), "犹豫": ("#f97316", "🤔"),
        "试探": ("#8b5cf6", "🔎"), "信任": ("#22c55e", "💚"),
        "心动": ("#ec4899", "💗"), "决定": ("#ef4444", "🎯"),
        "下单": ("#16a34a", "✅"),
    }
    for p in ctx['psychology']:
        state = p.get("mental_state", "")
        color, icon = ("#64748b", "📍")
        for key, val in psych_states.items():
            if key in state:
                color, icon = val
                break
        psych_html += f"""
            <div class="psych-item">
                <div class="psych-dot" style="background:{color};">{icon}</div>
                <div class="psych-line" style="border-color:{color}40;"></div>
                <div class="psych-content">
                    <span class="psych-state" style="color:{color};">{_esc(state)}</span>
                    <p><b>触发：</b>{_esc(p.get('trigger', ''))}</p>
                    <p><b>用户说：</b>{_esc(p.get('user_quote', ''))}</p>
                </div>
            </div>"""

    # ===== 模块5：关键因素 HTML =====
    kf = ctx['key_factors']
    key_sentence = _esc(kf.get("key_sentence", ""))
    deal_node = _esc(kf.get("deal_node", ""))
    top3 = kf.get("top3_strengths", []) or []
    key_html = ""
    if key_sentence:
        key_html += f'<div class="key-item"><span class="key-label">关键一句话</span><p class="key-sentence">{key_sentence}</p></div>'
    if deal_node:
        key_html += f'<div class="key-item"><span class="key-label">成交节点</span><p>{deal_node}</p></div>'
    if top3:
        strengths_html = "".join(f'<li>{_esc(s)}</li>' for s in top3)
        key_html += f'<div class="key-item"><span class="key-label">Top 3 优势</span><ul class="strength-list">{strengths_html}</ul></div>'

    # ===== 模块6：改进建议 HTML =====
    imp = ctx['improvements']
    flaws = imp.get("flaws", []) or []
    opt_suggestions = imp.get("optimization_suggestions", []) or []
    time_compression = _esc(imp.get("time_compression", ""))
    improv_html = ""
    if flaws:
        improv_html += f'<div class="improv-item"><b>瑕疵点：</b><ul>{"".join(f"<li>{_esc(f)}</li>" for f in flaws)}</ul></div>'
    if opt_suggestions:
        for opt in opt_suggestions:
            improv_html += f"""<div class="improv-item">
                <p><b>原语句：</b>{_esc(opt.get('original', ''))}</p>
                <p><b>更优方案：</b><span style="color:#22c55e;">{_esc(opt.get('better', ''))}</span></p>
            </div>"""
    if time_compression:
        improv_html += f'<div class="improv-item"><b>压缩成交时长：</b>{time_compression}</div>'

    # 聊天数据 JSON（转义）
    chat_json = json.dumps(ctx['chat_data'], ensure_ascii=False)

    # 生成时间
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{_esc(title)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;color:#1e293b;line-height:1.6;}}
.container{{max-width:900px;margin:0 auto;padding:20px;}}

/* 标题区 */
.report-header{{background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);color:#fff;padding:40px 30px;border-radius:12px;text-align:center;margin-bottom:24px;}}
.report-header h1{{font-size:24px;margin-bottom:8px;}}
.report-header .subtitle{{font-size:14px;opacity:0.85;}}

/* 卡片通用 */
.card{{background:#fff;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08);}}
.card-title{{font-size:18px;font-weight:700;color:#1e40af;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid #e2e8f0;display:flex;align-items:center;gap:8px;}}

/* 基础信息 */
.info-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;}}
.info-item{{padding:12px;background:#f8fafc;border-radius:8px;}}
.info-item .label{{font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;}}
.info-item .value{{font-size:15px;font-weight:600;color:#1e293b;margin-top:4px;}}

/* 用户画像 */
.profile-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;}}
.profile-item{{padding:14px;background:#f8fafc;border-radius:8px;border-left:3px solid #3b82f6;}}
.profile-item .label{{font-size:12px;color:#64748b;}}
.profile-item .value{{font-size:14px;color:#1e293b;margin-top:4px;}}

/* 流程时间轴 */
.timeline-item{{display:flex;gap:16px;padding:16px 0;position:relative;}}
.timeline-item:not(:last-child){{border-bottom:1px dashed #e2e8f0;}}
.timeline-icon{{width:40px;height:40px;border-radius:50%;background:#eff6ff;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;}}
.timeline-content{{flex:1;}}
.timeline-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}}
.timeline-header h4{{color:#1e40af;font-size:15px;}}
.timeline-time{{font-size:12px;color:#94a3b8;background:#f1f5f9;padding:2px 8px;border-radius:4px;}}
.timeline-body p{{font-size:14px;color:#475569;margin:4px 0;}}

/* 优秀话术高亮卡片 - RAG结构化条目 */
.highlight-card{{background:linear-gradient(135deg,#fef2f2,#fff1f2);border:1px solid #fecaca;border-radius:10px;padding:16px;margin-bottom:14px;}}
.highlight-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}}
.highlight-tag{{display:inline-block;background:#ef4444;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600;}}
.highlight-subject{{font-size:12px;color:#64748b;background:#f1f5f9;padding:2px 8px;border-radius:4px;}}
.highlight-dialog{{margin-bottom:12px;}}
.highlight-customer-q{{font-size:14px;color:#64748b;padding:8px 12px;background:#f8fafc;border-radius:6px;margin-bottom:6px;line-height:1.6;}}
.highlight-sales-a{{font-size:15px;color:#dc2626;font-weight:700;padding:10px 14px;background:#fff;border-radius:6px;border-left:3px solid #ef4444;line-height:1.7;}}
.highlight-meta{{margin-bottom:12px;padding:10px 12px;background:rgba(255,255,255,0.7);border-radius:6px;}}
.meta-row{{font-size:13px;color:#475569;margin:4px 0;line-height:1.6;}}
.risk-text{{color:#dc2626;font-weight:600;}}
.mini-tag{{display:inline-block;background:#dbeafe;color:#1d4ed8;font-size:11px;padding:1px 6px;border-radius:3px;margin-right:4px;}}
.highlight-analysis p{{font-size:13px;color:#475569;margin:4px 0;line-height:1.6;}}
.anti-pitfall{{color:#f59e0b;font-weight:600;}}

/* 心理变化曲线 */
.psych-item{{display:flex;gap:12px;padding:12px 0;position:relative;}}
.psych-dot{{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;}}
.psych-line{{position:absolute;left:17px;top:48px;width:2px;border-left:2px dashed;height:calc(100% - 36px);}}
.psych-item:last-child .psych-line{{display:none;}}
.psych-content{{flex:1;}}
.psych-state{{font-weight:700;font-size:14px;display:block;margin-bottom:4px;}}
.psych-content p{{font-size:13px;color:#475569;margin:2px 0;}}

/* 关键因素 */
.key-item{{padding:14px 0;border-bottom:1px solid #f1f5f9;}}
.key-item:last-child{{border-bottom:none;}}
.key-label{{font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px;}}
.key-sentence{{font-size:16px;color:#1e40af;font-weight:600;font-style:italic;padding:8px 14px;background:#eff6ff;border-radius:6px;border-left:3px solid #3b82f6;}}
.strength-list{{padding-left:20px;color:#475569;}}
.strength-list li{{margin:4px 0;}}

/* 改进建议 */
.improv-item{{padding:14px 0;border-bottom:1px solid #f1f5f9;}}
.improv-item:last-child{{border-bottom:none;}}
.improv-item p{{font-size:14px;color:#475569;margin:4px 0;}}
.improv-item ul{{padding-left:20px;color:#ef4444;}}
.improv-item li{{margin:3px 0;}}

/* 聊天记录区 */
.chat-section{{background:#fff;border-radius:12px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,0.08);}}
.chat-section .card-title{{margin-bottom:20px;}}
.chat-list{{list-style:none;padding:0;}}
.chat-item{{margin-bottom:16px;display:flex;align-items:flex-end;}}
.chat-item.user{{flex-direction:row;}}
.chat-item.sales{{flex-direction:row-reverse;}}
.chat-avatar{{width:40px;height:40px;border-radius:50%;object-fit:cover;flex-shrink:0;}}
.chat-bubble-wrap{{max-width:70%;margin:0 10px;}}
.chat-meta{{font-size:11px;color:#94a3b8;margin-bottom:4px;}}
.chat-item.user .chat-meta{{text-align:left;}}
.chat-item.sales .chat-meta{{text-align:right;}}
.chat-bubble{{padding:10px 14px;border-radius:12px;font-size:14px;line-height:1.6;word-break:break-word;white-space:pre-wrap;}}
.chat-item.user .chat-bubble{{background:#f1f5f9;color:#1e293b;border-top-left-radius:4px;}}
.chat-item.sales .chat-bubble{{background:#3b82f6;color:#fff;border-top-right-radius:4px;}}

/* 响应式 */
@media(max-width:600px){{
    .profile-grid{{grid-template-columns:1fr;}}
    .info-grid{{grid-template-columns:1fr 1fr;}}
    .container{{padding:12px;}}
}}
</style>
</head>
<body>
<div class="container">
    <!-- 标题区 -->
    <div class="report-header">
        <h1>{_esc(title)}</h1>
        <div class="subtitle">生成时间：{now} &nbsp;|&nbsp; 对话轮次：{msg_count} 条 &nbsp;|&nbsp; 聊天时长：{chat_duration}</div>
    </div>

    <!-- 模块1：基础信息 -->
    <div class="card">
        <div class="card-title">📋 案例基础信息</div>
        <div class="info-grid">
            <div class="info-item"><div class="label">成交时间</div><div class="value">{deal_time}</div></div>
            <div class="info-item"><div class="label">聊天总时长</div><div class="value">{chat_duration}</div></div>
            <div class="info-item"><div class="label">对话轮次</div><div class="value">{msg_count}</div></div>
            <div class="info-item"><div class="label">销售风格</div><div class="value">{sales_style}</div></div>
        </div>
    </div>

    <!-- 用户画像 -->
    <div class="card">
        <div class="card-title">👤 用户画像分析</div>
        <div class="profile-grid">
            <div class="profile-item"><div class="label">身份背景</div><div class="value">{identity}</div></div>
            <div class="profile-item"><div class="label">核心顾虑</div><div class="value">{concerns}</div></div>
            <div class="profile-item"><div class="label">真实需求</div><div class="value">{needs}</div></div>
            <div class="profile-item"><div class="label">关键痛点</div><div class="value">{pain_points}</div></div>
        </div>
    </div>

    <!-- 模块2：成交全链路拆解 -->
    <div class="card">
        <div class="card-title">🔗 成交全流程拆解（0 → 成交）</div>
        {journey_html}
    </div>

    <!-- 模块3：优秀话术萃取 -->
    <div class="card">
        <div class="card-title">⭐ 优秀话术萃取（标红高亮）</div>
        {scripts_html}
    </div>

    <!-- 模块4：用户心理变化曲线 -->
    <div class="card">
        <div class="card-title">📈 用户心理变化曲线</div>
        {psych_html}
    </div>

    <!-- 模块5：成交关键原因 -->
    <div class="card">
        <div class="card-title">🎯 本次成交关键原因</div>
        {key_html}
    </div>

    <!-- 模块6：改进建议 -->
    <div class="card">
        <div class="card-title">💡 可优化改进建议</div>
        {improv_html}
    </div>

    <!-- 原始聊天记录 -->
    <div class="chat-section">
        <div class="card-title">💬 完整原始聊天记录</div>
        <ul class="chat-list" id="chatList"></ul>
    </div>
</div>

<script>
var chatData = {chat_json};
var chatList = document.getElementById('chatList');

chatData.forEach(function(item) {{
    if (!item.sentence) return;
    var isSales = item.author === 'right';
    var li = document.createElement('li');
    li.className = 'chat-item ' + (isSales ? 'sales' : 'user');

    var avatarSrc = item.headimg || 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><circle cx="20" cy="20" r="20" fill="' + (isSales ? '%233b82f6' : '%2394a3b8') + '"/><text x="20" y="25" text-anchor="middle" fill="white" font-size="16">' + (isSales ? '销' : '客') + '</text></svg>');

    var time = (item.createTime || '').substring(0, 16);
    var name = isSales ? (item.nickName || '销售') : (item.nickName || '客户');

    li.innerHTML = '<img class="chat-avatar" src="' + avatarSrc + '" alt="avatar">' +
        '<div class="chat-bubble-wrap">' +
            '<div class="chat-meta">' + name + ' ' + time + '</div>' +
            '<div class="chat-bubble">' + escapeHtml(item.sentence) + '</div>' +
        '</div>';
    chatList.appendChild(li);
}});

function escapeHtml(text) {{
    if (typeof text !== 'string') return String(text);
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}}
</script>
</body>
</html>"""


def _esc(text) -> str:
    """HTML 转义"""
    if not text:
        return ""
    text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
