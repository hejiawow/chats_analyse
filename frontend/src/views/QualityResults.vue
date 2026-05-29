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
      <a-form-item label="时间范围">
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
        <a-select v-model:value="filters.risk_level" placeholder="全部" style="width: 120px" allowClear>
          <a-select-option value="high">高风险</a-select-option>
          <a-select-option value="medium">中风险</a-select-option>
          <a-select-option value="low">低风险</a-select-option>
          <a-select-option value="none">无风险</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="关键词">
        <a-select v-model:value="filters.keyword" placeholder="全部" style="width: 120px" allowClear showSearch>
          <a-select-option v-for="kw in keywordOptions" :key="kw" :value="kw">{{ kw }}</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item>
        <a-button type="primary" @click="handleSearch">查询</a-button>
        <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
        <a-button style="margin-left: 8px" @click="handleExport">导出 CSV</a-button>
      </a-form-item>
    </a-form>

    <!-- 结果表格 -->
    <a-table
      :columns="columns"
      :data-source="data"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      size="small"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
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
          <a-tag :color="getRiskColor(record.risk_level)">{{ getRiskText(record.risk_level) }}</a-tag>
        </template>
        <template v-if="column.key === 'detected_keywords'">
          <span :title="record.detected_keywords">{{ record.detected_keywords || '无' }}</span>
        </template>
        <template v-if="column.key === 'risk_description'">
          <span :title="record.risk_description">{{ record.risk_description || '-' }}</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" type="link" @click="showDetail(record)">详情</a-button>
        </template>
      </template>
    </a-table>

    <!-- 详情弹窗 -->
    <a-modal v-model:open="detailVisible" title="质检详情" width="750px">
      <a-descriptions v-if="detailData" :column="1" bordered size="small" :label-style="{ width: '120px', minWidth: '120px' }">
        <a-descriptions-item label="销售ID">{{ detailData.user_id }}</a-descriptions-item>
        <a-descriptions-item label="销售姓名">{{ detailData.user_name || '-' }}</a-descriptions-item>
        <a-descriptions-item label="好友ID">{{ detailData.friend_id }}</a-descriptions-item>
        <a-descriptions-item label="好友姓名">{{ detailData.friend_name || '-' }}</a-descriptions-item>
        <a-descriptions-item label="检测时间">{{ detailData.check_time_start }} ~ {{ detailData.check_time_end }}</a-descriptions-item>
        <a-descriptions-item label="聊天记录数">{{ detailData.chat_record_count }}</a-descriptions-item>
        <a-descriptions-item label="检测关键词">{{ detailData.detected_keywords || '无' }}</a-descriptions-item>
        <a-descriptions-item v-if="detailData.keyword_matches && detailData.keyword_matches.length" label="关键词匹配">
          <div v-for="(m, idx) in detailData.keyword_matches" :key="idx" style="margin-bottom: 8px">
            <div><strong>{{ m.keyword }}</strong> - {{ m.speaker }} - {{ m.time }}</div>
            <div style="color: #666">{{ m.message }}</div>
          </div>
        </a-descriptions-item>
        <a-descriptions-item v-if="detailData.risk_level" label="风险等级">
          <a-tag :color="getRiskColor(detailData.risk_level)">{{ getRiskText(detailData.risk_level) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item v-if="detailData.risk_category" label="风险类别">{{ detailData.risk_category }}</a-descriptions-item>
        <a-descriptions-item label="风险描述">
          <pre style="white-space: pre-wrap; margin: 0; word-break: break-word">{{ detailData.risk_description || '-' }}</pre>
        </a-descriptions-item>
        <a-descriptions-item label="建议措施">
          <pre style="white-space: pre-wrap; margin: 0; word-break: break-word">{{ detailData.suggested_action || '-' }}</pre>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import { getQualityCheckList, getQualityCheckStats, exportQualityCheckResults, getActiveKeywords } from '@/api/qualitycheck'

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

// 关键词选项列表（用于筛选下拉框）
const keywordOptions = ref([])

// 筛选
const filters = reactive({ user_id: '', friend_id: '', risk_level: null, keyword: '', timeRange: null })

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
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '销售', key: 'user_name', width: 140 },
  { title: '好友', key: 'friend_name', width: 140 },
  { title: '风险等级', key: 'risk_level', width: 100 },
  { title: '检测关键词', key: 'detected_keywords', width: 150, ellipsis: true },
  { title: '风险描述', key: 'risk_description', ellipsis: true },
  { title: '风险类别', dataIndex: 'risk_category', key: 'risk_category', width: 100 },
  { title: '操作', key: 'actions', width: 80, fixed: 'right' },
]

// 详情
const detailVisible = ref(false)
const detailData = ref(null)

// 风险等级映射
function getRiskColor(level) {
  const map = { high: 'error', medium: 'warning', low: 'blue', none: 'success' }
  return map[level] || 'default'
}

function getRiskText(level) {
  const map = { high: '高风险', medium: '中风险', low: '低风险', none: '无风险' }
  return map[level] || '未知'
}

// 加载统计
async function loadStats() {
  try {
    stats.value = await getQualityCheckStats()
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
        if (typeof timestamp === 'number' && Date.now() - timestamp < KEYWORDS_CACHE_TTL) {
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
    keywordOptions.value = res.data || []
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
    keywordOptions.value = []
  }
}

// 加载列表
async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.friend_id) params.friend_id = filters.friend_id
    if (filters.risk_level) params.risk_level = filters.risk_level
    if (filters.keyword) params.keyword = filters.keyword
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
  filters.risk_level = null
  filters.keyword = ''
  filters.timeRange = null
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
}

// 导出
async function handleExport() {
  try {
    const params = {}
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.friend_id) params.friend_id = filters.friend_id
    if (filters.risk_level) params.risk_level = filters.risk_level
    if (filters.keyword) params.keyword = filters.keyword
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
  margin-bottom: 16px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}
</style>