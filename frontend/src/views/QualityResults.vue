<template>
  <div class="page-card quality-results-page">
    <!-- 统计卡片 -->
    <div class="qr-stats-cards">
      <a-card class="qr-stat-card" size="small">
        <a-statistic title="总数" :value="stats.total" />
      </a-card>
      <a-card class="qr-stat-card high" size="small">
        <a-statistic title="高风险" :value="stats.risk_distribution?.high || 0" :value-style="{ color: '#ef4444' }" />
      </a-card>
      <a-card class="qr-stat-card medium" size="small">
        <a-statistic title="中风险" :value="stats.risk_distribution?.medium || 0" :value-style="{ color: '#f59e0b' }" />
      </a-card>
      <a-card class="qr-stat-card low" size="small">
        <a-statistic title="低风险" :value="stats.risk_distribution?.low || 0" :value-style="{ color: '#3b82f6' }" />
      </a-card>
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
    <a-form layout="inline" :model="filters" class="qr-filter-bar">
      <a-form-item label="聊天时间范围">
        <a-range-picker
          v-model:value="filters.timeRange"
          :show-time="{ format: 'HH:mm:ss' }"
          format="YYYY-MM-DD HH:mm:ss"
          :placeholder="['开始时间', '结束时间']"
          style="width: 340px"
        />
      </a-form-item>
      <a-form-item label="销售ID">
        <a-input v-model:value="filters.user_id" placeholder="销售ID" style="width: 140px" />
      </a-form-item>
      <a-form-item label="好友ID">
        <a-input v-model:value="filters.friend_id" placeholder="好友ID" style="width: 140px" />
      </a-form-item>
      <a-form-item label="风险等级">
        <a-checkbox-group v-model:value="filters.risk_levels" :options="riskLevelOptions" />
      </a-form-item>
<!--             <a-form-item> -->
      <a-form-item label="关键词">
        <a-select v-model:value="filters.keyword" placeholder="全部" style="width: 120px" allowClear showSearch>
          <a-select-option v-for="kw in keywordOptions" :key="kw" :value="kw">{{ kw }}</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="触发方">
        <a-select v-model:value="filters.trigger_party" placeholder="全部" style="width: 120px" allowClear>
          <a-select-option value="sales">销售触发</a-select-option>
          <a-select-option value="customer">客户触发</a-select-option>
          <a-select-option value="both">双方触发</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item>
        <a-button type="primary" @click="handleSearch">查询</a-button>
        <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
        <a-button style="margin-left: 8px" @click="handleExport">导出 CSV</a-button>
      </a-form-item>
    </a-form>

    <!-- 关键词筛选折叠面板 -->
    <a-collapse v-model:activeKey="keywordsCollapseActive" class="qr-keywords-collapse">
      <a-collapse-panel key="keywords" header="关键词筛选（点击展开）">
        <a-checkbox-group v-model:value="filters.keywords">
          <div class="qr-keywords-table-layout">
            <!-- 类别标题行 -->
            <div class="qr-keywords-header-row">
              <div v-for="(keywords, category) in keywordOptions" :key="category" class="qr-keywords-header-cell">
                {{ categoryNames[category] || category }}
              </div>
            </div>

            <!-- 关键词内容行 -->
            <div class="qr-keywords-content-row">
              <div v-for="(keywords, category) in keywordOptions" :key="category" class="qr-keywords-content-cell">
                <a-checkbox v-for="kw in keywords" :key="kw" :value="kw" class="qr-keyword-checkbox-vertical">
                  {{ kw }}
                </a-checkbox>
              </div>
            </div>
          </div>
        </a-checkbox-group>
      </a-collapse-panel>
    </a-collapse>

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
          <span>{{ formatDateTime(record.created_at) }}</span>
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
            <a-tag v-if="record.modified_risk_level" color="purple" size="small" style="margin-left: 4px; font-size: 10px; padding: 0 3px">改</a-tag>
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
        <template v-if="column.key === 'risk_description'">
          <span :title="record.risk_description">{{ record.risk_description || '-' }}</span>
        </template>
        <template v-if="column.key === 'remark'">
          <span :title="record.remark">{{ record.remark || '-' }}</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" type="link" @click="showDetail(record)">详情</a-button>
        </template>
      </template>
    </a-table>

    <!-- 详情弹窗 -->
    <a-modal style="top: 20px" v-model:open="detailVisible" title="质检详情" width="750px" :footer="null" :closable="true">
      <div v-if="detailData">
        <!-- 非编辑模式 -->
        <div v-if="!editMode">
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
                <a-tag v-if="detailData.modified_risk_level" color="purple" style="margin-left: 4px">已修正</a-tag>
              </div>
              <div v-if="detailData.modified_risk_level" style="font-size: 12px; color: #999; margin-top: 4px">
                原始等级: {{ getRiskText(detailData.risk_level) }}
              </div>
            </a-descriptions-item>
            <a-descriptions-item v-if="detailData.trigger_party" label="触发方">
              <a-tag :color="getTriggerPartyColor(detailData.trigger_party)">
                {{ getTriggerPartyText(detailData.trigger_party) }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item v-if="detailData.risk_category" label="风险类别">{{ detailData.risk_category }}</a-descriptions-item>
            <a-descriptions-item label="风险描述">
              <pre style="white-space: pre-wrap; margin: 0; word-break: break-word">{{ detailData.risk_description || '-' }}</pre>
            </a-descriptions-item>
            <a-descriptions-item label="建议措施">
              <pre style="white-space: pre-wrap; margin: 0; word-break: break-word">{{ detailData.suggested_action || '-' }}</pre>
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
              </a-select>
              <span v-if="editForm.risk_level !== detailData.risk_level" style="margin-left: 8px; color: #999; font-size: 12px">
                (原始: {{ getRiskText(detailData.risk_level) }})
              </span>
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
          <span v-if="detailData" style="margin-left: 12px; color: #666">
            时间范围：{{ formatDateTime(detailData.check_time_start) }} ~ {{ formatDateTime(detailData.check_time_end) }}
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
import { ref, reactive, onMounted, watch, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import { getQualityCheckList, getQualityCheckStats, exportQualityCheckResults, getActiveKeywords, getQualityCheckChatRecords, updateQualityCheckResult, getQualityCheckModificationLogs } from '@/api/qualitycheck'

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
  keywords: [],      // 关键词数组
  trigger_party: undefined,
  timeRange: null
})

// 关键词折叠面板状态（默认折叠）
const keywordsCollapseActive = ref([])

// 风险等级选项配置
const riskLevelOptions = [
  { label: '高风险', value: 'high' },
  { label: '中风险', value: 'medium' },
  { label: '低风险', value: 'low' },
  { label: '无风险', value: 'none' }
]
// const filters = reactive({ user_id: '', friend_id: '', risk_level: null, keyword: '', trigger_party: undefined, timeRange: null })

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

const columns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', minWidth: 160, ellipsis: true},
  { title: '销售', key: 'user_name', minWidth: 130, ellipsis: true },
  { title: '好友', key: 'friend_name', minWidth: 130, ellipsis: true },
  { title: '好友备注', dataIndex: 'chat_title', key: 'chat_title', minWidth: 120, ellipsis: true },
  { title: '好友别名', dataIndex: 'alias', key: 'alias', minWidth: 120, ellipsis: true },
  { title: '绑定手机号', dataIndex: 'phone', key: 'phone', minWidth: 130, ellipsis: true },
  { title: '备注手机号', dataIndex: 'remark_phone', key: 'remark_phone', minWidth: 130, ellipsis: true },
  { title: '风险等级', key: 'risk_level', minWidth: 100 },
  { title: '触发方', dataIndex: 'trigger_party', key: 'trigger_party', width: 100 },
  { title: '检测关键词', key: 'detected_keywords', minWidth: 150, ellipsis: true },
  { title: '风险描述', key: 'risk_description', ellipsis: true }, // 无宽度，自适应
  { title: '风险类别', dataIndex: 'risk_category', key: 'risk_category', minWidth: 100 },
  { title: '备注', dataIndex: 'remark', key: 'remark', width: 150, ellipsis: true },
  { title: '操作', key: 'actions', width: 80, fixed: 'right' },
]

// 详情
const detailVisible = ref(false)
const detailData = ref(null)

// 编辑模式
const editMode = ref(false)
const editForm = reactive({
  risk_level: '',
  remark: ''
})
const editLoading = ref(false)

// 聊天记录弹窗
const chatRecordsVisible = ref(false)
const chatRecordsLoading = ref(false)
const chatRecordsData = ref([])
const chatRecordsTotal = ref(0)

// 修改记录弹窗
const modificationLogsVisible = ref(false)
const modificationLogsLoading = ref(false)
const modificationLogsData = ref([])

// 风险等级映射
function getRiskColor(level) {
  const map = { high: 'error', medium: 'warning', low: 'blue', none: 'success' }
  return map[level] || 'default'
}

function getRiskText(level) {
  const map = { high: '高风险', medium: '中风险', low: '低风险', none: '无风险' }
  return map[level] || '未知'
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

// 加载统计（响应筛选条件，但不包括风险等级）
async function loadStats() {
  try {
    const params = {}
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.friend_id) params.friend_id = filters.friend_id
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.trigger_party) params.trigger_party = filters.trigger_party
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
    if (filters.timeRange && filters.timeRange.length === 2) {
      params.start_time = filters.timeRange[0].format('YYYY-MM-DD HH:mm:ss')
      params.end_time = filters.timeRange[1].format('YYYY-MM-DD HH:mm:ss')
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
//   filters.risk_level = null
//   filters.keyword = ''
  filters.trigger_party = undefined
  filters.timeRange = null
  keywordsCollapseActive.value = []  // 折叠关键词面板
  pagination.current = 1
  loadData()
  loadStats()
}

// 分页
function handleTableChange(pag) {
  pagination.current = pag.current
  loadData()
}

// 详情
function showDetail(record) {
  detailData.value = record
  detailVisible.value = true
  editMode.value = false
}

// 进入编辑模式
function enterEditMode() {
  editForm.risk_level = detailData.value.modified_risk_level || detailData.value.risk_level
  editForm.remark = detailData.value.remark || ''
  editMode.value = true
}

// 取消编辑
function cancelEdit() {
  editMode.value = false
}

// 保存编辑
async function saveEdit() {
  editLoading.value = true
  try {
    const res = await updateQualityCheckResult(detailData.value.id, {
      risk_level: editForm.risk_level,
      remark: editForm.remark
    })
    if (res.error) {
      message.error(res.error)
    } else {
      message.success('修改成功')
      detailData.value = res.data
      editMode.value = false
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
  try {
    const res = await getQualityCheckChatRecords(detailData.value.id)
    chatRecordsData.value = res.data || []
    chatRecordsTotal.value = res.total || 0
  } catch {
    chatRecordsData.value = []
    chatRecordsTotal.value = 0
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

/* 统计卡片 */
.qr-stats-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.qr-stat-card {
  flex: 1;
  border-radius: 8px;
}

.qr-stat-card.high {
  border-left: 3px solid #ef4444;
}

.qr-stat-card.medium {
  border-left: 3px solid #f59e0b;
}

.qr-stat-card.low {
  border-left: 3px solid #3b82f6;
}

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
  padding: 16px 20px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
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

/* 关键词筛选折叠面板 */
.qr-keywords-collapse {
  margin-bottom: 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

/* 关键词表格布局 */
.qr-keywords-table-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 类别标题行 */
.qr-keywords-header-row {
  display: flex;
  gap: 0;
  border-bottom: 2px solid #e2e8f0;
}

.qr-keywords-header-cell {
  flex: 1;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  text-align: center;
  background: #f8fafc;
}

/* 关键词内容行 */
.qr-keywords-content-row {
  display: flex;
  gap: 0;
}

.qr-keywords-content-cell {
  flex: 1;
  padding: 8px 12px;
  min-width: 120px;
}

/* 关键词checkbox垂直排列并确保对齐 */
.qr-keyword-checkbox-vertical {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}

.qr-keyword-checkbox-vertical:last-child {
  margin-bottom: 0;
}

/* 确保Ant Design Vue的checkbox内容对齐 */
.qr-keywords-content-cell .ant-checkbox-wrapper {
  display: flex;
  align-items: center;
}

.qr-keywords-content-cell .ant-checkbox {
  margin-right: 8px;
}

.qr-keywords-content-cell .ant-checkbox + span {
  padding-right: 0;
  line-height: 1.5;
}
</style>