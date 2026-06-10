<template>
  <div class="page-card quality-results-page">
    <!-- 统计卡片 -->
    <div class="qr-stats-cards">
      <div class="qr-stat-chip">
        <span class="qr-stat-label">总数</span>
        <span class="qr-stat-value">{{ stats.total }}</span>
      </div>
      <div class="qr-stat-chip high">
        <span class="qr-stat-label">高风险</span>
        <span class="qr-stat-value">{{ stats.risk_distribution?.high || 0 }}</span>
      </div>
      <div class="qr-stat-chip medium">
        <span class="qr-stat-label">中风险</span>
        <span class="qr-stat-value">{{ stats.risk_distribution?.medium || 0 }}</span>
      </div>
      <div class="qr-stat-chip low">
        <span class="qr-stat-label">低风险</span>
        <span class="qr-stat-value">{{ stats.risk_distribution?.low || 0 }}</span>
      </div>
      <div class="qr-stat-chip p0">
        <span class="qr-stat-label">P0 立即</span>
        <span class="qr-stat-value">{{ stats.priority_distribution?.P0 || 0 }}</span>
      </div>
      <div class="qr-stat-chip p1">
        <span class="qr-stat-label">P1 今日</span>
        <span class="qr-stat-value">{{ stats.priority_distribution?.P1 || 0 }}</span>
      </div>
      <div class="qr-stat-chip p2">
        <span class="qr-stat-label">P2 复核</span>
        <span class="qr-stat-value">{{ stats.priority_distribution?.P2 || 0 }}</span>
      </div>
      <div class="qr-stat-chip p3">
        <span class="qr-stat-label">P3 观察</span>
        <span class="qr-stat-value">{{ stats.priority_distribution?.P3 || 0 }}</span>
      </div>
    </div>

    <!-- 可折叠统计详情 -->
    <a-collapse class="qr-stats-collapse" v-model:activeKey="collapseActiveKey">
      <a-collapse-panel key="charts" header="统计详情（点击展开）">
        <div class="qr-charts-row">
          <div class="qr-chart-box">
            <div class="qr-chart-title">风险分布</div>
            <div ref="pieChartRef" class="qr-chart"></div>
          </div>
          <div class="qr-chart-box">
            <div class="qr-chart-title">关键词 TOP10</div>
            <div ref="barChartRef" class="qr-chart"></div>
          </div>
        </div>
      </a-collapse-panel>
    </a-collapse>

    <!-- 筛选栏 -->
    <a-form :model="filters" class="qr-filter-bar">
      <div class="qr-filter-fields">
        <a-form-item label="时间范围">
          <a-range-picker
            v-model:value="filters.timeRange"
            :show-time="{ format: 'HH:mm:ss' }"
            format="YYYY-MM-DD HH:mm:ss"
            :placeholder="['开始', '结束']"
            style="width: 280px"
          />
        </a-form-item>
        <a-form-item label="销售ID">
          <a-input v-model:value="filters.user_id" placeholder="请输入" style="width: 120px" allowClear />
        </a-form-item>
        <a-form-item label="好友ID">
          <a-input v-model:value="filters.friend_id" placeholder="请输入" style="width: 120px" allowClear />
        </a-form-item>
        <a-form-item label="触发方">
          <a-select v-model:value="filters.trigger_party" placeholder="全部" style="width: 100px" allowClear>
            <a-select-option value="sales">销售</a-select-option>
            <a-select-option value="customer">客户</a-select-option>
            <a-select-option value="both">双方</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="风险等级">
          <a-select
            v-model:value="filters.risk_levels"
            mode="multiple"
            placeholder="请选择"
            style="width: 180px"
            allowClear
            :maxTagCount="1"
            :maxTagPlaceholder="omittedValues => `+${omittedValues.length}个`"
          >
            <a-select-option value="high">高风险</a-select-option>
            <a-select-option value="medium">中风险</a-select-option>
            <a-select-option value="low">低风险</a-select-option>
            <a-select-option value="none">无风险</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="关键词">
          <a-select
            v-model:value="filters.keywords"
            mode="multiple"
            placeholder="请选择"
            style="width: 180px"
            allowClear
            :maxTagCount="1"
            :maxTagPlaceholder="omittedValues => `+${omittedValues.length}个`"
            showSearch
            :filterOption="filterKeywordOption"
          >
            <a-select-opt-group v-for="(keywords, category) in keywordOptions" :key="category">
              <template #label>{{ categoryNames[category] || category }}</template>
              <a-select-option v-for="kw in keywords" :key="kw" :value="kw">{{ kw }}</a-select-option>
            </a-select-opt-group>
          </a-select>
        </a-form-item>
        <a-form-item label="风险类别">
          <a-select
            v-model:value="filters.risk_categories"
            mode="multiple"
            placeholder="请选择"
            style="width: 200px"
            allowClear
            :maxTagCount="1"
            :maxTagPlaceholder="omittedValues => `+${omittedValues.length}个`"
          >
            <a-select-option value="投诉">投诉</a-select-option>
            <a-select-option value="退款">退款</a-select-option>
            <a-select-option value="取消订单">取消订单</a-select-option>
            <a-select-option value="监管介入">监管介入</a-select-option>
            <a-select-option value="虚假宣传">虚假宣传</a-select-option>
            <a-select-option value="服务不满">服务不满</a-select-option>
            <a-select-option value="其他">其他</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="优先级">
          <a-select
            v-model:value="filters.action_priorities"
            mode="multiple"
            placeholder="请选择"
            style="width: 180px"
            allowClear
            :maxTagCount="1"
            :maxTagPlaceholder="omittedValues => `+${omittedValues.length}个`"
          >
            <a-select-option value="P0">P0 立即</a-select-option>
            <a-select-option value="P1">P1 今日</a-select-option>
            <a-select-option value="P2">P2 复核</a-select-option>
            <a-select-option value="P3">P3 观察</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="责任方">
          <a-select v-model:value="filters.recommended_owner" placeholder="全部" style="width: 120px" allowClear>
            <a-select-option value="质检">质检</a-select-option>
            <a-select-option value="销售主管">销售主管</a-select-option>
            <a-select-option value="客服">客服</a-select-option>
            <a-select-option value="法务">法务</a-select-option>
            <a-select-option value="无需处理">无需处理</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="动作类型">
          <a-select v-model:value="filters.action_type" placeholder="全部" style="width: 130px" allowClear>
            <a-select-option value="立即介入">立即介入</a-select-option>
            <a-select-option value="主管复核">主管复核</a-select-option>
            <a-select-option value="客服跟进">客服跟进</a-select-option>
            <a-select-option value="销售安抚">销售安抚</a-select-option>
            <a-select-option value="培训复盘">培训复盘</a-select-option>
            <a-select-option value="误报观察">误报观察</a-select-option>
            <a-select-option value="无需处理">无需处理</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="人工复核">
          <a-select v-model:value="filters.needs_manual_review" placeholder="全部" style="width: 110px" allowClear>
            <a-select-option :value="true">需要</a-select-option>
            <a-select-option :value="false">不需要</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="处理状态">
          <a-select v-model:value="filters.process_status" placeholder="全部" style="width: 130px" allowClear>
            <a-select-option value="pending">待处理</a-select-option>
            <a-select-option value="processing">处理中</a-select-option>
            <a-select-option value="resolved">已处理</a-select-option>
            <a-select-option value="false_positive">误报</a-select-option>
            <a-select-option value="escalated">已升级</a-select-option>
          </a-select>
        </a-form-item>
      </div>
      <div class="qr-filter-actions-row">
        <a-button type="primary" @click="handleSearch">查询</a-button>
        <a-button @click="handleReset">重置</a-button>
        <a-button @click="handleExport">导出 CSV</a-button>
      </div>
    </a-form>

    <!-- 列设置 -->
    <div class="qr-table-toolbar">
      <a-button
        type="primary"
        @click="handleAutoBatchReview"
        :loading="autoReviewing"
        style="margin-right: 12px"
      >
        一键审查
      </a-button>
      <a-popover
        v-model:open="columnSettingsOpen"
        title="列显示设置"
        trigger="click"
        placement="bottomRight"
        :overlay-style="{ width: '280px' }"
      >
        <template #content>
          <div class="qr-column-settings">
            <a-checkbox-group
              v-model:value="visibleKeysArray"
              :options="columnOptions"
              class="qr-column-checkboxes"
            />
            <div class="qr-column-settings-footer">
              <a-button size="small" @click="resetColumns">重置默认</a-button>
              <a-button size="small" type="primary" @click="columnSettingsOpen = false">确定</a-button>
            </div>
          </div>
        </template>
        <a-button size="small">
          <SettingOutlined /> 列设置
        </a-button>
      </a-popover>
    </div>

    <!-- 结果表格 -->
    <a-table
      :columns="columns"
      :data-source="data"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      size="small"
      @change="handleTableChange"
      :scroll="{ x: 'max-content' }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'created_at'">
          <div class="qr-time-cell">
            <span class="qr-time-date">{{ formatDate(record.created_at) }}</span>
            <span class="qr-time-hms">{{ formatTime(record.created_at) }}</span>
          </div>
        </template>
        <template v-if="column.key === 'user_name'">
          <div>
            <div>{{ record.user_name || '-' }}</div>
            <div style="color: #999; font-size: 12px">{{ record.user_id }}</div>
          </div>
        </template>
        <template v-if="column.key === 'friend_name'">
          <div>
            <div>{{ record.friend_name || '-' }}</div>
            <div style="color: #999; font-size: 12px">{{ record.friend_id }}</div>
          </div>
        </template>
        <template v-if="column.key === 'risk_level'">
          <div>
            <a-tag :color="getRiskColor(record.display_risk_level || record.risk_level)">
              {{ getRiskText(record.display_risk_level || record.risk_level) }}
            </a-tag>
            <a-tag v-if="record.modified_risk_level && record.modified_risk_level !== ''" color="purple" size="small" style="margin-left: 4px; font-size: 10px; padding: 0 3px">改</a-tag>
          </div>
        </template>
        <template v-if="column.key === 'trigger_party'">
          <a-tag :color="getTriggerPartyColor(record.trigger_party)">
            {{ getTriggerPartyText(record.trigger_party) }}
          </a-tag>
        </template>
        <template v-if="column.key === 'detected_keywords'">
          <span :title="record.detected_keywords">{{ record.detected_keywords || '无' }}</span>
        </template>
        <template v-if="column.key === 'issue_summary'">
          <a-tooltip v-if="record.issue_summary" placement="topLeft" :overlayStyle="{ maxWidth: '520px' }">
            <template #title>
              <span class="summary-tooltip-text">{{ record.issue_summary }}</span>
            </template>
            <span class="table-risk-desc clickable-summary">{{ record.issue_summary }}</span>
          </a-tooltip>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'chat_title'">
          <a-tooltip v-if="record.chat_title" placement="topLeft" :overlayStyle="{ maxWidth: '400px' }">
            <template #title>
              <span>{{ record.chat_title }}</span>
            </template>
            <span class="table-chat-title">{{ record.chat_title }}</span>
          </a-tooltip>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'action_priority'">
          <a-tag :color="getPriorityColor(record.action_priority)">
            {{ getPriorityText(record.action_priority) }}
          </a-tag>
        </template>
        <template v-if="column.key === 'recommended_owner'">
          <a-tag :color="getOwnerColor(record.recommended_owner)">
            {{ record.recommended_owner || '-' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'action_type'">
          <span>{{ record.action_type || '-' }}</span>
        </template>
        <template v-if="column.key === 'process_status'">
          <a-tag :color="getProcessStatusColor(record.process_status)">
            {{ getProcessStatusText(record.process_status) }}
          </a-tag>
        </template>
        <template v-if="column.key === 'has_secondary_review'">
          <a-tag v-if="record.has_secondary_review" color="green">已审查</a-tag>
          <a-tag v-else color="default">未审查</a-tag>
        </template>
        <template v-if="column.key === 'remark'">
          <span :title="record.remark">{{ record.remark || '-' }}</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" type="link" @click="showDetail(record)">详情</a-button>
          <a-button size="small" type="link" @click="showEdit(record)">编辑</a-button>
        </template>
      </template>
    </a-table>

    <!-- 详情弹窗 -->
    <a-modal style="top: 20px" v-model:open="detailVisible" title="质检详情" width="750px" :footer="null" :closable="true">
      <div v-if="detailData">
        <!-- 非编辑模式 -->
        <div v-if="!editMode">
          <div class="guidance-panel">
            <div class="guidance-head">
              <div>
                <div class="guidance-title">{{ detailData.issue_summary || '暂无问题摘要' }}</div>
                <div class="guidance-subtitle">
                  {{ detailData.risk_category || '其他' }} · {{ getTriggerPartyText(detailData.trigger_party) }}触发
                </div>
              </div>
              <div class="guidance-tags">
                <a-tag :color="getPriorityColor(detailData.action_priority)">{{ getPriorityText(detailData.action_priority) }}</a-tag>
                <a-tag :color="getOwnerColor(detailData.recommended_owner)">{{ detailData.recommended_owner || '未分配' }}</a-tag>
                <a-tag :color="getProcessStatusColor(detailData.process_status)">{{ getProcessStatusText(detailData.process_status) }}</a-tag>
              </div>
            </div>
            <div class="guidance-grid">
              <div class="guidance-item">
                <span class="guidance-label">风险原因</span>
                <p>{{ detailData.guidance?.risk_reason || '-' }}</p>
              </div>
              <div class="guidance-item">
                <span class="guidance-label">客户诉求</span>
                <p>{{ detailData.guidance?.customer_intent || '-' }}</p>
              </div>
              <div class="guidance-item">
                <span class="guidance-label">立即动作</span>
                <p>{{ detailData.guidance?.immediate_action || detailData.action_type || '-' }}</p>
              </div>
              <div class="guidance-item">
                <span class="guidance-label">处理时限</span>
                <p>{{ detailData.follow_up_deadline || '-' }}</p>
              </div>
              <div class="guidance-item full">
                <div class="guidance-copy-row">
                  <span class="guidance-label">建议话术</span>
                  <a-button size="small" type="link" @click="copyReplySuggestion">复制</a-button>
                </div>
                <p>{{ detailData.guidance?.reply_suggestion || '-' }}</p>
              </div>
              <div class="guidance-item">
                <span class="guidance-label">培训建议</span>
                <p>{{ detailData.guidance?.training_suggestion || '-' }}</p>
              </div>
              <div class="guidance-item">
                <span class="guidance-label">升级原因</span>
                <p>{{ detailData.guidance?.escalation_reason || '-' }}</p>
              </div>
            </div>
          </div>
          <a-descriptions :column="1" bordered size="small" :label-style="{ width: '120px', minWidth: '120px' }">
            <a-descriptions-item label="销售ID">{{ detailData.user_id }}</a-descriptions-item>
            <a-descriptions-item label="销售姓名">{{ detailData.user_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="好友ID">{{ detailData.friend_id }}</a-descriptions-item>
            <a-descriptions-item label="好友姓名">{{ detailData.friend_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="好友备注">{{ detailData.chat_title || '-' }}</a-descriptions-item>
            <a-descriptions-item label="好友别名">{{ detailData.alias || '-' }}</a-descriptions-item>
            <a-descriptions-item label="绑定手机号">{{ detailData.phone || '-' }}</a-descriptions-item>
            <a-descriptions-item label="备注手机号">{{ detailData.remark_phone || '-' }}</a-descriptions-item>
            <a-descriptions-item label="检测时间">{{ formatDateTime(detailData.check_time_start) }} ~ {{ formatDateTime(detailData.check_time_end) }}</a-descriptions-item>
            <a-descriptions-item label="聊天记录数">{{ detailData.chat_record_count }}</a-descriptions-item>
            <a-descriptions-item label="检测关键词">{{ detailData.detected_keywords || '无' }}</a-descriptions-item>
            <a-descriptions-item v-if="detailData.keyword_matches && detailData.keyword_matches.length" label="关键词匹配">
              <div v-for="(m, idx) in detailData.keyword_matches" :key="idx" style="margin-bottom: 8px">
                <div><strong>{{ m.keyword }}</strong> - {{ m.speaker }} - {{ m.time }}</div>
                <div style="color: #666">{{ m.message }}</div>
              </div>
              <a-button type="link" size="small" @click="showChatRecords" style="margin-top: 8px">查看全部聊天记录</a-button>
            </a-descriptions-item>
            <a-descriptions-item v-else label="聊天记录">
              <a-button type="link" size="small" @click="showChatRecords">查看全部聊天记录</a-button>
            </a-descriptions-item>
            <a-descriptions-item v-if="detailData.risk_level" label="风险等级">
              <div>
                <a-tag :color="getRiskColor(detailData.display_risk_level || detailData.risk_level)">
                  {{ getRiskText(detailData.display_risk_level || detailData.risk_level) }}
                </a-tag>
                <a-tag v-if="detailData.modified_risk_level && detailData.modified_risk_level !== ''" color="purple" style="margin-left: 4px">已修正</a-tag>
              </div>
              <div v-if="detailData.modified_risk_level && detailData.modified_risk_level !== ''" style="font-size: 12px; color: #999; margin-top: 4px">
                原始等级: {{ getRiskText(detailData.risk_level) }}
              </div>
            </a-descriptions-item>
            <a-descriptions-item v-if="detailData.trigger_party" label="触发方">
              <a-tag :color="getTriggerPartyColor(detailData.trigger_party)">
                {{ getTriggerPartyText(detailData.trigger_party) }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item v-if="detailData.risk_category" label="风险类别">{{ detailData.risk_category }}</a-descriptions-item>
            <a-descriptions-item label="问题摘要">
              <pre style="white-space: pre-wrap; margin: 0; word-break: break-word">{{ detailData.issue_summary || '-' }}</pre>
            </a-descriptions-item>
            <a-descriptions-item label="处理建议">
              <div class="processing-line">
                <a-tag :color="getPriorityColor(detailData.action_priority)">{{ getPriorityText(detailData.action_priority) }}</a-tag>
                <span>{{ detailData.recommended_owner || '-' }}</span>
                <span>{{ detailData.action_type || '-' }}</span>
                <span>{{ detailData.follow_up_deadline || '-' }}</span>
                <a-tag v-if="detailData.needs_manual_review" color="red">需人工复核</a-tag>
                <a-tag v-else color="green">无需人工复核</a-tag>
              </div>
            </a-descriptions-item>
            <a-descriptions-item v-if="detailData.key_evidence && detailData.key_evidence.length" label="关键证据">
              <div v-for="(e, idx) in detailData.key_evidence" :key="idx" class="evidence-item">
                <div class="evidence-meta">{{ e.speaker || '-' }} · {{ e.time || '-' }}</div>
                <div class="evidence-content">{{ e.content || '-' }}</div>
                <div v-if="e.reason" class="evidence-reason">{{ e.reason }}</div>
              </div>
            </a-descriptions-item>
            <a-descriptions-item label="备注">
              <pre style="white-space: pre-wrap; margin: 0; word-break: break-word">{{ detailData.remark || '-' }}</pre>
            </a-descriptions-item>
          </a-descriptions>
          <div style="margin-top: 16px; text-align: right">
            <a-button @click="showModificationLogs" style="margin-right: 8px">修改记录</a-button>
            <a-button type="primary" @click="enterEditMode">编辑</a-button>
          </div>
        </div>
        <!-- 编辑模式 -->
        <div v-else>
          <a-descriptions :column="1" bordered size="small" :label-style="{ width: '120px', minWidth: '120px' }">
            <a-descriptions-item label="销售ID">{{ detailData.user_id }}</a-descriptions-item>
            <a-descriptions-item label="好友ID">{{ detailData.friend_id }}</a-descriptions-item>
            <a-descriptions-item label="风险等级">
              <a-select v-model:value="editForm.risk_level" style="width: 120px">
                <a-select-option value="high">高风险</a-select-option>
                <a-select-option value="medium">中风险</a-select-option>
                <a-select-option value="low">低风险</a-select-option>
                <a-select-option value="none">无风险</a-select-option>
                <a-select-option value="unknown">未知</a-select-option>
              </a-select>
              <span v-if="editForm.risk_level !== detailData.risk_level" style="margin-left: 8px; color: #999; font-size: 12px">
                (原始: {{ getRiskText(detailData.risk_level) }})
              </span>
            </a-descriptions-item>
            <a-descriptions-item label="处理状态">
              <a-select v-model:value="editForm.process_status" style="width: 160px">
                <a-select-option value="pending">待处理</a-select-option>
                <a-select-option value="processing">处理中</a-select-option>
                <a-select-option value="resolved">已处理</a-select-option>
                <a-select-option value="false_positive">误报</a-select-option>
                <a-select-option value="escalated">已升级</a-select-option>
              </a-select>
            </a-descriptions-item>
            <a-descriptions-item label="备注">
              <a-textarea v-model:value="editForm.remark" :rows="3" placeholder="请输入备注" />
            </a-descriptions-item>
          </a-descriptions>
          <div style="margin-top: 16px; text-align: right">
            <a-button @click="cancelEdit" style="margin-right: 8px">取消</a-button>
            <a-button type="primary" :loading="editLoading" @click="saveEdit">保存</a-button>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 聊天记录弹窗 -->
    <a-modal style="top: 20px" v-model:open="chatRecordsVisible" title="全部聊天记录" width="900px" :footer="null" :closable="true">
      <div v-if="chatRecordsLoading" style="text-align: center; padding: 40px">
        <a-spin />
      </div>
      <div v-else-if="chatRecordsData.length === 0" style="text-align: center; padding: 40px; color: #999">
        暂无聊天记录
      </div>
      <div v-else class="chat-records-list">
        <div class="chat-records-header">
          共 {{ chatRecordsTotal }} 条聊天记录
          <span v-if="chatRecordsTimeRange" style="margin-left: 12px; color: #666">
            时间范围：{{ formatDateTime(chatRecordsTimeRange.start) }} ~ {{ formatDateTime(chatRecordsTimeRange.end) }}
          </span>
        </div>
        <div class="chat-records-content">
          <div v-for="(msg, idx) in chatRecordsData" :key="idx" class="chat-message" :class="{ 'is-self': msg.author === 'right' }">
            <div class="chat-message-time" v-if="shouldShowTime(idx)">
              {{ formatChatTime(msg.createTime) }}
            </div>
            <div class="chat-message-row">
              <div class="chat-avatar" :class="{ 'self-avatar': msg.author === 'right' }">
                {{ msg.author === 'right' ? '销' : '客' }}
              </div>
              <div class="chat-bubble">
                <div class="chat-bubble-content">{{ msg.sentence }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <a-button @click="chatRecordsVisible = false">关闭</a-button>
      </template>
    </a-modal>

    <!-- 修改记录弹窗 -->
    <a-modal style="top: 20px" v-model:open="modificationLogsVisible" title="修改记录" width="700px" :footer="null">
      <div v-if="modificationLogsLoading" style="text-align: center; padding: 40px">
        <a-spin />
      </div>
      <div v-else>
        <a-timeline>
          <!-- AI原始判断 -->
          <a-timeline-item color="green">
            <div style="margin-bottom: 8px">
              <strong>AI智能质检</strong>
              <a-tag color="green" size="small" style="margin-left: 8px">初始</a-tag>
            </div>
            <div>
              风险等级：<a-tag :color="getRiskColor(detailData.risk_level)" size="small">{{ getRiskText(detailData.risk_level) }}</a-tag>
            </div>
          </a-timeline-item>
          <!-- 人工修改记录 -->
          <a-timeline-item v-for="(log, idx) in modificationLogsData" :key="idx" :color="idx === 0 ? 'blue' : 'gray'">
            <div style="margin-bottom: 8px">
              <strong>{{ log.user_name || log.user_id }}</strong>
              <span style="color: #999; margin-left: 8px">{{ formatModTime(log.modified_at) }}</span>
            </div>
            <div v-if="log.old_risk_level !== log.new_risk_level" style="margin-bottom: 4px">
              风险等级：<a-tag :color="getRiskColor(log.old_risk_level)" size="small">{{ getRiskText(log.old_risk_level) }}</a-tag>
              <span style="margin: 0 4px">→</span>
              <a-tag :color="getRiskColor(log.new_risk_level)" size="small">{{ getRiskText(log.new_risk_level) }}</a-tag>
            </div>
            <div v-if="log.old_remark !== log.new_remark">
              <div style="margin-bottom: 4px; color: #666">备注修改：</div>
              <div v-if="log.old_remark" style="margin-bottom: 4px; padding: 8px; background: #f5f5f5; border-radius: 4px">
                <div style="color: #999; font-size: 12px; margin-bottom: 4px">原备注：</div>
                <pre style="white-space: pre-wrap; margin: 0; word-break: break-word">{{ log.old_remark }}</pre>
              </div>
              <div v-if="log.new_remark" style="padding: 8px; background: #e6f7ff; border-radius: 4px">
                <div style="color: #999; font-size: 12px; margin-bottom: 4px">新备注：</div>
                <pre style="white-space: pre-wrap; margin: 0; word-break: break-word">{{ log.new_remark }}</pre>
              </div>
            </div>
          </a-timeline-item>
        </a-timeline>
      </div>
      <template #footer>
        <a-button @click="modificationLogsVisible = false">关闭</a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, nextTick, computed } from 'vue'
import { message } from 'ant-design-vue'
import { SettingOutlined } from '@ant-design/icons-vue'
import * as echarts from 'echarts'
import { getQualityCheckList, getQualityCheckStats, exportQualityCheckResults, getActiveKeywords, getQualityCheckChatRecords, updateQualityCheckResult, getQualityCheckModificationLogs, getQualityCheckDetail } from '@/api/qualitycheck'
import { autoBatchReview } from '@/api/qualityreview'

// 关键词缓存配置
const KEYWORDS_CACHE_KEY = 'qc_keywords_cache'
const KEYWORDS_CACHE_TTL = 3600000 // 1 小时（毫秒）

// 统计数据
const stats = ref({ total: 0, risk_distribution: {}, keyword_frequency: [] })
const collapseActiveKey = ref([])
const pieChartRef = ref(null)
const barChartRef = ref(null)
let pieChart = null
let barChart = null

// 关键词选项列表（用于筛选下拉框，按类别分组）
const keywordOptions = ref({})

// 类别名称映射
const categoryNames = {
  'refund': '退款相关',
  'complaint': '投诉相关',
  'order_cancel': '取消订单',
  'regulatory': '监管机构',
  'fraud': '欺诈相关'
}

// 筛选
const filters = reactive({
  user_id: '',
  friend_id: '',
  risk_levels: [],   // 风险等级数组
  risk_categories: [], // 风险类别数组
  keywords: [],      // 关键词数组
  trigger_party: undefined,
  action_priorities: [],  // 优先级数组
  recommended_owner: undefined,
  action_type: undefined,
  needs_manual_review: undefined,
  process_status: undefined,
  timeRange: null
})

// 关键词下拉框搜索过滤函数
function filterKeywordOption(input, option) {
  return option.value.toLowerCase().includes(input.toLowerCase())
}

// 表格
const data = ref([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 20,
  showSizeChanger: false,
  showTotal: (total) => `共 ${total} 条`,
  total: 0
})

// 排序状态
const sortState = reactive({
  field: null,
  order: null  // 'ascend' | 'descend' | null
})

const allColumns = [
  { title: '销售', key: 'user_name', minWidth: 130, ellipsis: true, fixed: 'left' },
  { title: '好友', key: 'friend_name', minWidth: 130, ellipsis: true },
  { title: '时间', dataIndex: 'created_at', key: 'created_at', minWidth: 120, ellipsis: true, sorter: true },
  { title: '好友备注', dataIndex: 'chat_title', key: 'chat_title', width: 130 },
  { title: '好友别名', dataIndex: 'alias', key: 'alias', minWidth: 120, ellipsis: true },
  { title: '绑定手机号', dataIndex: 'phone', key: 'phone', minWidth: 130, ellipsis: true },
  { title: '备注手机号', dataIndex: 'remark_phone', key: 'remark_phone', minWidth: 130, ellipsis: true },
  { title: '风险等级', dataIndex: 'risk_level', key: 'risk_level', minWidth: 100, sorter: true },
  { title: '触发方', dataIndex: 'trigger_party', key: 'trigger_party', width: 100 },
  { title: '问题摘要', key: 'issue_summary', width: 220 },
  { title: '优先级', dataIndex: 'action_priority', key: 'action_priority', minWidth: 90, sorter: true },
  { title: '责任方', key: 'recommended_owner', minWidth: 100 },
  { title: '动作类型', key: 'action_type', minWidth: 110, ellipsis: true },
  { title: '处理状态', key: 'process_status', minWidth: 100 },
  { title: '检测关键词', key: 'detected_keywords', minWidth: 150, ellipsis: true },
  { title: '风险类别', dataIndex: 'risk_category', key: 'risk_category', minWidth: 100 },
  { title: '二次审查', dataIndex: 'has_secondary_review', key: 'has_secondary_review', width: 100 },
  { title: '备注', dataIndex: 'remark', key: 'remark', width: 150, ellipsis: true },
  { title: '操作', key: 'actions', width: 90, fixed: 'right' },
]

// 列显示配置
const COLUMN_CONFIG_KEY = 'qr_visible_columns'
const allColumnKeys = allColumns.map(c => c.key)

function loadVisibleColumns() {
  try {
    const test = '__test__'
    localStorage.setItem(test, test)
    localStorage.removeItem(test)
  } catch {
    return new Set(allColumnKeys)
  }
  try {
    const saved = localStorage.getItem(COLUMN_CONFIG_KEY)
    if (saved) {
      const keys = JSON.parse(saved)
      if (Array.isArray(keys) && keys.length > 0 && keys.some(k => allColumnKeys.includes(k))) {
        return new Set(keys)
      }
    }
  } catch { /* 忽略 */ }
  return new Set(allColumnKeys)
}

const visibleColumnKeys = ref(loadVisibleColumns())

function saveVisibleColumns() {
  try {
    localStorage.setItem(COLUMN_CONFIG_KEY, JSON.stringify([...visibleColumnKeys.value]))
  } catch { /* 忽略 */ }
}

// 实际传给 a-table 的列（过滤后的）
const columns = computed(() => {
  return allColumns.filter(col => {
    // 操作列和销售列始终显示
    if (col.key === 'actions') return true
    if (col.fixed === 'left') return true
    return visibleColumnKeys.value.has(col.key)
  })
})

// checkbox 绑定的数组形式
const visibleKeysArray = computed({
  get: () => [...visibleColumnKeys.value],
  set: (val) => {
    visibleColumnKeys.value = new Set(val)
    saveVisibleColumns()
  }
})

// 列设置面板的选项列表
const columnOptions = computed(() => {
  return allColumns
    .filter(c => c.key !== 'actions' && c.fixed !== 'left')
    .map(c => ({ label: c.title, value: c.key }))
})

const columnSettingsOpen = ref(false)

function resetColumns() {
  visibleColumnKeys.value = new Set(allColumnKeys)
  saveVisibleColumns()
}

// 详情
const detailVisible = ref(false)
const detailData = ref(null)

// 编辑模式
const editMode = ref(false)
const editFromDetail = ref(false)  // 标记编辑入口是否来自详情弹窗
const editForm = reactive({
  risk_level: '',
  process_status: 'pending',
  remark: ''
})
const editLoading = ref(false)

// 聊天记录弹窗
const chatRecordsVisible = ref(false)
const chatRecordsLoading = ref(false)
const chatRecordsData = ref([])
const chatRecordsTotal = ref(0)
const chatRecordsTimeRange = ref(null)

// 修改记录弹窗
const modificationLogsVisible = ref(false)
const modificationLogsLoading = ref(false)
const modificationLogsData = ref([])

// 一键审查
const autoReviewing = ref(false)

// 风险等级映射
function getRiskColor(level) {
  const map = { high: 'error', medium: 'warning', low: 'blue', none: 'success', unknown: 'default' }
  return map[level] || 'default'
}

function getRiskText(level) {
  const map = { high: '高风险', medium: '中风险', low: '低风险', none: '无风险', unknown: '未知' }
  return map[level] || '未知'
}

// 格式化日期部分 YYYY-MM-DD
function formatDate(isoString) {
  if (!isoString) return '-'
  try {
    const date = new Date(isoString)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  } catch {
    return isoString
  }
}

// 格式化时间部分 HH:mm:ss
function formatTime(isoString) {
  if (!isoString) return ''
  try {
    const date = new Date(isoString)
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    const second = String(date.getSeconds()).padStart(2, '0')
    return `${hour}:${minute}:${second}`
  } catch {
    return ''
  }
}

// 时间格式化：将 ISO 格式转为 YYYY-MM-DD HH:mm:ss
function formatDateTime(isoString) {
  if (!isoString) return '-'
  try {
    const date = new Date(isoString)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    const second = String(date.getSeconds()).padStart(2, '0')
    return `${year}-${month}-${day} ${hour}:${minute}:${second}`
  } catch {
    return isoString
  }
}
// 触发方颜色映射
const getTriggerPartyColor = (trigger_party) => {
  const colorMap = {
    'sales': 'blue',
    'customer': 'orange',
    'both': 'purple',
  }
  return colorMap[trigger_party] || 'default'
}

// 触发方文本映射
const getTriggerPartyText = (trigger_party) => {
  const textMap = {
    'sales': '销售',
    'customer': '客户',
    'both': '双方',
  }
  return textMap[trigger_party] || '无'
}

const getPriorityColor = (priority) => {
  const colorMap = {
    P0: 'red',
    P1: 'orange',
    P2: 'blue',
    P3: 'green'
  }
  return colorMap[priority] || 'default'
}

const getPriorityText = (priority) => {
  const textMap = {
    P0: 'P0 立即',
    P1: 'P1 今日',
    P2: 'P2 复核',
    P3: 'P3 观察'
  }
  return textMap[priority] || '未定'
}

const getOwnerColor = (owner) => {
  const colorMap = {
    '质检': 'geekblue',
    '销售主管': 'purple',
    '客服': 'cyan',
    '法务': 'red',
    '无需处理': 'green'
  }
  return colorMap[owner] || 'default'
}

const getProcessStatusColor = (status) => {
  const colorMap = {
    pending: 'gold',
    processing: 'blue',
    resolved: 'green',
    false_positive: 'default',
    escalated: 'red'
  }
  return colorMap[status] || 'default'
}

const getProcessStatusText = (status) => {
  const textMap = {
    pending: '待处理',
    processing: '处理中',
    resolved: '已处理',
    false_positive: '误报',
    escalated: '已升级'
  }
  return textMap[status] || '未定'
}

// 一键审查所有未审查的高中风险结果
async function handleAutoBatchReview() {
  autoReviewing.value = true
  try {
    const res = await autoBatchReview()
    message.success(res.message)
    loadData()
    loadStats()
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '一键审查失败'
    message.error(detail)
  } finally {
    autoReviewing.value = false
  }
}

// 加载统计（响应筛选条件，但不包括风险等级）
async function loadStats() {
  try {
    const params = {}
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.friend_id) params.friend_id = filters.friend_id
    if (filters.keywords && filters.keywords.length > 0) params.keywords = filters.keywords
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.trigger_party) params.trigger_party = filters.trigger_party
    if (filters.action_priorities && filters.action_priorities.length > 0) params.action_priorities = filters.action_priorities
    if (filters.risk_categories && filters.risk_categories.length > 0) params.risk_categories = filters.risk_categories
    if (filters.recommended_owner) params.recommended_owner = filters.recommended_owner
    if (filters.action_type) params.action_type = filters.action_type
    if (filters.needs_manual_review !== undefined) params.needs_manual_review = filters.needs_manual_review
    if (filters.process_status) params.process_status = filters.process_status
    if (filters.timeRange && filters.timeRange.length === 2) {
      params.start_time = filters.timeRange[0].format('YYYY-MM-DD HH:mm:ss')
      params.end_time = filters.timeRange[1].format('YYYY-MM-DD HH:mm:ss')
    }
    // 注意：不传递 risk_level，统计不受风险等级筛选影响
    stats.value = await getQualityCheckStats(params)
    if (collapseActiveKey.value.includes('charts')) {
      nextTick(() => renderCharts())
    }
  } catch {
    stats.value = { total: 0, risk_distribution: {}, keyword_frequency: [] }
  }
}

// 渲染图表
function renderCharts() {
  if (!pieChartRef.value || !barChartRef.value) return

  // 风险分布饼图
  if (!pieChart) pieChart = echarts.init(pieChartRef.value)
  const distribution = stats.value.risk_distribution || {}
  pieChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 10 },
    series: [{
      type: 'pie',
      radius: ['35%', '60%'],
      center: ['50%', '40%'],
      data: [
        { value: distribution.high || 0, name: '高风险', itemStyle: { color: '#ef4444' } },
        { value: distribution.medium || 0, name: '中风险', itemStyle: { color: '#f59e0b' } },
        { value: distribution.low || 0, name: '低风险', itemStyle: { color: '#3b82f6' } },
        { value: distribution.none || 0, name: '无风险', itemStyle: { color: '#10b981' } },
      ]
    }]
  })

  // 关键词柱状图
  if (!barChart) barChart = echarts.init(barChartRef.value)
  const keywords = stats.value.keyword_frequency || []
  barChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 100, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: keywords.map(k => k.keyword).reverse() },
    series: [{
      type: 'bar',
      data: keywords.map(k => k.count).reverse(),
      itemStyle: { color: '#6366f1' }
    }]
  })
}

// localStorage availability check
function isLocalStorageAvailable() {
  try {
    const test = '__test__'
    localStorage.setItem(test, test)
    localStorage.removeItem(test)
    return true
  } catch {
    return false
  }
}

// 加载关键词列表（带本地缓存）
async function loadKeywords() {
  // 尝试从 localStorage 获取（仅当可用时）
  if (isLocalStorageAvailable()) {
    const cached = localStorage.getItem(KEYWORDS_CACHE_KEY)
    if (cached) {
      try {
        const { data, timestamp } = JSON.parse(cached)
        // 检查缓存是否过期，且数据格式是否正确（必须是对象，不能是数组）
        if (typeof timestamp === 'number' && Date.now() - timestamp < KEYWORDS_CACHE_TTL && typeof data === 'object' && !Array.isArray(data)) {
          keywordOptions.value = data
          return
        }
      } catch {
        // 解析失败，忽略缓存
      }
    }
  }

  try {
    const res = await getActiveKeywords()
    keywordOptions.value = res.data || {}  // 现在是对象
    // 存入 localStorage（仅当可用时）
    if (isLocalStorageAvailable()) {
      try {
        localStorage.setItem(KEYWORDS_CACHE_KEY, JSON.stringify({
          data: keywordOptions.value,
          timestamp: Date.now()
        }))
      } catch {
        // 存储失败（如 quota exceeded），忽略
      }
    }
  } catch {
    keywordOptions.value = {}
  }
}

// 加载列表
async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.friend_id) params.friend_id = filters.friend_id
    if (filters.risk_levels && filters.risk_levels.length > 0) params.risk_levels = filters.risk_levels
    if (filters.keywords && filters.keywords.length > 0) params.keywords = filters.keywords
//     if (filters.risk_level) params.risk_level = filters.risk_level
//     if (filters.keyword) params.keyword = filters.keyword
    if (filters.trigger_party) params.trigger_party = filters.trigger_party
    if (filters.action_priorities && filters.action_priorities.length > 0) params.action_priorities = filters.action_priorities
    if (filters.risk_categories && filters.risk_categories.length > 0) params.risk_categories = filters.risk_categories
    if (filters.recommended_owner) params.recommended_owner = filters.recommended_owner
    if (filters.action_type) params.action_type = filters.action_type
    if (filters.needs_manual_review !== undefined) params.needs_manual_review = filters.needs_manual_review
    if (filters.process_status) params.process_status = filters.process_status
    if (filters.timeRange && filters.timeRange.length === 2) {
      params.start_time = filters.timeRange[0].format('YYYY-MM-DD HH:mm:ss')
      params.end_time = filters.timeRange[1].format('YYYY-MM-DD HH:mm:ss')
    }
    if (sortState.field && sortState.order) {
      params.sort_field = sortState.field
      params.sort_order = sortState.order
    }
    const res = await getQualityCheckList(params)
    data.value = res.data || []
    pagination.total = res.total || 0
  } catch {
    data.value = []
  } finally {
    loading.value = false
  }
}

// 搜索
function handleSearch() {
  pagination.current = 1
  loadData()
  loadStats()
}

// 重置
function handleReset() {
  filters.user_id = ''
  filters.friend_id = ''
  filters.risk_levels = []
  filters.keywords = []
  filters.trigger_party = undefined
  filters.action_priorities = []
  filters.risk_categories = []
  filters.recommended_owner = undefined
  filters.action_type = undefined
  filters.needs_manual_review = undefined
  filters.process_status = undefined
  filters.timeRange = null
  sortState.field = null
  sortState.order = null
  pagination.current = 1
  loadData()
  loadStats()
}

async function copyReplySuggestion() {
  const text = detailData.value?.guidance?.reply_suggestion || ''
  if (!text) {
    message.warning('暂无可复制话术')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    message.success('话术已复制')
  } catch {
    message.error('复制失败')
  }
}

// 分页 + 排序
function handleTableChange(pag, _filters, sorter) {
  pagination.current = pag.current
  const sortField = sorter?.field || sorter?.columnKey
  if (sortField) {
    sortState.field = sortField
    sortState.order = sorter.order || null
  } else {
    sortState.field = null
    sortState.order = null
  }
  loadData()
}

// 详情
async function showDetail(record) {
  detailVisible.value = true
  editMode.value = false
  // 调用详情API获取完整数据（包含大字段）
  try {
    const res = await getQualityCheckDetail(record.id)
    if (res.error) {
      detailData.value = record  // 如果API失败，使用列表数据
    } else {
      detailData.value = res
    }
  } catch {
    detailData.value = record  // 如果API失败，使用列表数据
  }
}

// 从表格直接打开编辑模式
function showEdit(record) {
  detailData.value = record
  editForm.risk_level = record.modified_risk_level || record.risk_level
  editForm.process_status = record.process_status || 'pending'
  editForm.remark = record.remark || ''
  editFromDetail.value = false  // 标记来源为表格
  editMode.value = true
  detailVisible.value = true
}

// 从详情弹窗进入编辑模式
function enterEditMode() {
  editForm.risk_level = detailData.value.modified_risk_level || detailData.value.risk_level
  editForm.process_status = detailData.value.process_status || 'pending'
  editForm.remark = detailData.value.remark || ''
  editFromDetail.value = true  // 标记来源为详情弹窗
  editMode.value = true
}

// 取消编辑
function cancelEdit() {
  editMode.value = false
  if (!editFromDetail.value) {
    // 从表格进入的编辑，关闭弹窗
    detailVisible.value = false
  }
}

// 保存编辑
async function saveEdit() {
  editLoading.value = true
  try {
    const res = await updateQualityCheckResult(detailData.value.id, {
      risk_level: editForm.risk_level,
      process_status: editForm.process_status,
      remark: editForm.remark
    })
    if (res.error) {
      message.error(res.error)
    } else {
      message.success('修改成功')
      detailData.value = res.data
      editMode.value = false
      if (!editFromDetail.value) {
        // 从表格进入的编辑，关闭弹窗
        detailVisible.value = false
      }
      // 刷新列表数据
      loadData()
      loadStats()
    }
  } catch {
    message.error('修改失败')
  } finally {
    editLoading.value = false
  }
}

// 查看聊天记录
async function showChatRecords() {
  if (!detailData.value) return
  chatRecordsVisible.value = true
  chatRecordsLoading.value = true
  chatRecordsData.value = []
  chatRecordsTimeRange.value = null
  try {
    const res = await getQualityCheckChatRecords(detailData.value.id)
    chatRecordsData.value = res.data || []
    chatRecordsTotal.value = res.total || 0
    chatRecordsTimeRange.value = res.time_range || null
  } catch {
    chatRecordsData.value = []
    chatRecordsTotal.value = 0
    chatRecordsTimeRange.value = null
  } finally {
    chatRecordsLoading.value = false
  }
}

// 查看修改记录
async function showModificationLogs() {
  if (!detailData.value) return
  modificationLogsVisible.value = true
  modificationLogsLoading.value = true
  modificationLogsData.value = []
  try {
    const res = await getQualityCheckModificationLogs(detailData.value.id)
    modificationLogsData.value = res.data || []
  } catch {
    modificationLogsData.value = []
  } finally {
    modificationLogsLoading.value = false
  }
}

// 判断是否需要显示时间（相邻消息间隔超过5分钟显示时间）
function shouldShowTime(idx) {
  if (idx === 0) return true
  const prevTime = chatRecordsData.value[idx - 1]?.createTime
  const currTime = chatRecordsData.value[idx]?.createTime
  if (!prevTime || !currTime) return false

  const prevDate = new Date(prevTime)
  const currDate = new Date(currTime)
  const diffMinutes = (currDate - prevDate) / (1000 * 60)
  return diffMinutes >= 5
}

// 格式化聊天时间
function formatChatTime(time) {
  if (!time) return ''
  const date = new Date(time)
  const today = new Date()
  const isToday = date.toDateString() === today.toDateString()

  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')

  if (isToday) {
    return `${hours}:${minutes}`
  }
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  return `${month}-${day} ${hours}:${minutes}`
}

// 格式化修改记录时间（2026-06-03 15:41:10）
function formatModTime(time) {
  if (!time) return ''
  const date = new Date(time)
  const year = date.getFullYear()
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

// 导出
async function handleExport() {
  try {
    const params = {}
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.friend_id) params.friend_id = filters.friend_id
    if (filters.risk_levels && filters.risk_levels.length > 0) params.risk_levels = filters.risk_levels
    if (filters.keywords && filters.keywords.length > 0) params.keywords = filters.keywords
//     if (filters.risk_level) params.risk_level = filters.risk_level
//     if (filters.keyword) params.keyword = filters.keyword
    if (filters.trigger_party) params.trigger_party = filters.trigger_party
    if (filters.action_priorities && filters.action_priorities.length > 0) params.action_priorities = filters.action_priorities
    if (filters.risk_categories && filters.risk_categories.length > 0) params.risk_categories = filters.risk_categories
    if (filters.recommended_owner) params.recommended_owner = filters.recommended_owner
    if (filters.action_type) params.action_type = filters.action_type
    if (filters.needs_manual_review !== undefined) params.needs_manual_review = filters.needs_manual_review
    if (filters.process_status) params.process_status = filters.process_status
    if (filters.timeRange && filters.timeRange.length === 2) {
      params.start_time = filters.timeRange[0].format('YYYY-MM-DD HH:mm:ss')
      params.end_time = filters.timeRange[1].format('YYYY-MM-DD HH:mm:ss')
    }

    const blob = await exportQualityCheckResults(params)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'quality_check_results.csv'
    a.click()
    window.URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch {
    message.error('导出失败')
  }
}

// 监听折叠面板展开，渲染图表
watch(collapseActiveKey, (keys) => {
  if (keys.includes('charts')) {
    nextTick(() => renderCharts())
  }
})

// 监听风险等级变化，自动触发筛选
watch(() => filters.risk_levels, (newVal, oldVal) => {
  // 避免初始化时触发（oldVal为undefined）
  if (oldVal !== undefined && newVal !== oldVal) {
    handleSearch()
  }
})

// 监听关键词变化，自动触发筛选
watch(() => filters.keywords, (newVal, oldVal) => {
  if (oldVal !== undefined && newVal !== oldVal) {
    handleSearch()
  }
})

// 监听风险类别变化，自动触发筛选
watch(() => filters.risk_categories, (newVal, oldVal) => {
  if (oldVal !== undefined && newVal !== oldVal) {
    handleSearch()
  }
})

// 监听优先级变化，自动触发筛选
watch(() => filters.action_priorities, (newVal, oldVal) => {
  if (oldVal !== undefined && newVal !== oldVal) {
    handleSearch()
  }
})

onMounted(() => {
  loadStats()
  loadKeywords()
  loadData()
})
</script>

<style scoped>
.quality-results-page {
  width: 100%;
}

/* 统计卡片 - 紧凑布局 */
.qr-stats-cards {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.qr-stat-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  transition: box-shadow 0.2s;
}

.qr-stat-chip:hover {
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}

.qr-stat-chip.high {
  border-left: 3px solid #ef4444;
}

.qr-stat-chip.medium {
  border-left: 3px solid #f59e0b;
}

.qr-stat-chip.low {
  border-left: 3px solid #3b82f6;
}

.qr-stat-chip.p0 {
  border-left: 3px solid #dc2626;
}

.qr-stat-chip.p1 {
  border-left: 3px solid #ea580c;
}

.qr-stat-chip.p2 {
  border-left: 3px solid #2563eb;
}

.qr-stat-chip.p3 {
  border-left: 3px solid #16a34a;
}

.qr-stat-label {
  font-size: 12px;
  color: #64748b;
}

.qr-stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
  font-variant-numeric: tabular-nums;
}

.qr-stat-chip.high .qr-stat-value { color: #ef4444; }
.qr-stat-chip.medium .qr-stat-value { color: #f59e0b; }
.qr-stat-chip.low .qr-stat-value { color: #3b82f6; }
.qr-stat-chip.p0 .qr-stat-value { color: #dc2626; }
.qr-stat-chip.p1 .qr-stat-value { color: #ea580c; }
.qr-stat-chip.p2 .qr-stat-value { color: #2563eb; }
.qr-stat-chip.p3 .qr-stat-value { color: #16a34a; }

/* 可折叠面板 */
.qr-stats-collapse {
  margin-bottom: 20px;
  background: #fff;
  border-radius: 8px;
}

.qr-charts-row {
  display: flex;
  gap: 24px;
  padding: 16px 0;
}

.qr-chart-box {
  flex: 1;
}

.qr-chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 12px;
}

.qr-chart {
  height: 200px;
}

/* 筛选栏 */
.qr-filter-bar {
  margin-bottom: 5px;
  padding: 12px 20px 14px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

/* 筛选字段区域 - 自适应布局 */
.qr-filter-fields {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 4px 12px;
  width: 100%;
}

.qr-filter-fields .ant-form-item {
  margin-bottom: 8px;
  margin-right: 0;
  flex-shrink: 0;
}

.qr-filter-actions-row {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 4px;
  border-top: 1px solid #f1f5f9;
}

.guidance-panel {
  margin-bottom: 14px;
  padding: 14px 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #f8fafc;
}

.guidance-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.guidance-title {
  font-size: 16px;
  font-weight: 600;
  color: #102a43;
  line-height: 1.5;
  word-break: break-word;
}

.guidance-subtitle {
  margin-top: 2px;
  font-size: 12px;
  color: #627d98;
}

.guidance-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px;
  min-width: 180px;
}

.guidance-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.guidance-item {
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
}

.guidance-item.full {
  grid-column: 1 / -1;
}

.guidance-label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #486581;
}

.guidance-item p {
  margin: 0;
  color: #243b53;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.guidance-copy-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.processing-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.evidence-item {
  padding: 10px;
  margin-bottom: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
}

.evidence-meta {
  margin-bottom: 4px;
  font-size: 12px;
  color: #627d98;
}

.evidence-content {
  color: #243b53;
  line-height: 1.6;
  word-break: break-word;
}

.evidence-reason {
  margin-top: 6px;
  padding-left: 8px;
  border-left: 2px solid #3b82f6;
  color: #486581;
  font-size: 12px;
  line-height: 1.5;
}

.clickable-summary {
  cursor: help;
  border-bottom: 1px dotted #94a3b8;
}

.summary-tooltip-text {
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 720px) {
  .guidance-head {
    display: block;
  }

  .guidance-tags {
    justify-content: flex-start;
    margin-top: 8px;
  }

  .guidance-grid {
    grid-template-columns: 1fr;
  }

  .qr-filter-actions-row {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .qr-filter-fields .ant-form-item {
    flex: 1 1 100%;
  }

  .qr-filter-fields .ant-form-item .ant-input,
  .qr-filter-fields .ant-form-item .ant-select {
    width: 100% !important;
  }
}

/* 聊天记录弹窗样式 - 微信风格 */
.chat-records-list {
  max-height: 1000px;
}

.chat-records-header {
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
  color: #334155;
}

.chat-records-content {
  padding: 16px;
  max-height: 800px;
  overflow-y: auto;
  background: #ededed;
}

.chat-message {
  margin-bottom: 12px;
}

.chat-message-time {
  text-align: center;
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.chat-message-row {
  display: flex;
  align-items: flex-start;
}

.chat-message.is-self .chat-message-row {
  flex-direction: row-reverse;
}

.chat-avatar {
  width: 36px;
  height: 36px;
  border-radius: 4px;
  background: #e0e0e0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: #666;
  flex-shrink: 0;
}

.chat-avatar.self-avatar {
  background: #07c160;
  color: #fff;
}

.chat-bubble {
  max-width: 70%;
  margin: 0 10px;
  position: relative;
}

.chat-bubble-content {
  padding: 10px 14px;
  background: #fff;
  border-radius: 4px;
  font-size: 14px;
  color: #333;
  line-height: 1.5;
  word-break: break-word;
  box-shadow: 0 1px 1px rgba(0, 0, 0, 0.1);
}

.chat-message.is-self .chat-bubble-content {
  background: #95ec69;
}

/* 气泡小箭头 */
.chat-bubble::before {
  content: '';
  position: absolute;
  top: 10px;
  width: 0;
  height: 0;
  border: 6px solid transparent;
}

.chat-message:not(.is-self) .chat-bubble::before {
  left: -10px;
  border-right-color: #fff;
}

.chat-message.is-self .chat-bubble::before {
  right: -10px;
  border-left-color: #95ec69;
}

/* 风险描述/建议措施预览样式：限制高度，超长省略 */
.risk-desc-preview {
  white-space: pre-wrap;
  margin: 0;
  word-break: break-word;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  cursor: pointer;
}

/* 列设置工具栏 */
.qr-table-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.qr-column-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 360px;
  overflow-y: auto;
}

.qr-column-settings-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

/* 时间双行展示 */
.qr-time-cell {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.qr-time-date {
  font-size: 13px;
  color: #334155;
}

.qr-time-hms {
  font-size: 12px;
  color: #94a3b8;
}

/* 表格好友备注列：小字体、最多两行 */
.table-chat-title {
  font-size: 12px;
  color: #555;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  word-break: break-word;
  line-height: 1.4;
  cursor: help;
}

/* 表格风险描述列：小字体、最多两行 */
.table-risk-desc {
  font-size: 12px;
  color: #666;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  word-break: break-word;
  line-height: 1.4;
}
</style>
