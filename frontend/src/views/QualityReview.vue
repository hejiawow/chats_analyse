<template>
  <div class="quality-review">
    <!-- 筛选区 -->
    <a-card :bordered="false" style="margin-bottom: 16px">
      <a-form layout="inline" :model="filters">
        <a-form-item label="审查状态">
          <a-select
            v-model:value="filters.review_status"
            placeholder="全部"
            style="width: 120px"
            allowClear
          >
            <a-select-option value="completed">已完成</a-select-option>
            <a-select-option value="failed">失败</a-select-option>
            <a-select-option value="pending">待审查</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="风险类型">
          <a-select
            v-model:value="filters.risk_type"
            placeholder="全部"
            style="width: 100px"
            allowClear
          >
            <a-select-option value="退费">退费</a-select-option>
            <a-select-option value="投诉">投诉</a-select-option>
            <a-select-option value="其他">其他</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="优先级">
          <a-select
            v-model:value="filters.priority"
            placeholder="全部"
            style="width: 90px"
            allowClear
          >
            <a-select-option value="P0">P0</a-select-option>
            <a-select-option value="P1">P1</a-select-option>
            <a-select-option value="P2">P2</a-select-option>
            <a-select-option value="P3">P3</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="二次风险等级">
          <a-select
            v-model:value="filters.secondary_risk_level"
            placeholder="全部"
            style="width: 120px"
            allowClear
          >
            <a-select-option value="high">高风险</a-select-option>
            <a-select-option value="medium">中风险</a-select-option>
            <a-select-option value="low">低风险</a-select-option>
            <a-select-option value="none">无风险</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="是否确认">
          <a-select
            v-model:value="filters.confirmed"
            placeholder="全部"
            style="width: 90px"
            allowClear
          >
            <a-select-option :value="true">是</a-select-option>
            <a-select-option :value="false">否</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="批次ID">
          <a-input
            v-model:value="filters.batch_id"
            placeholder="请输入批次ID"
            style="width: 150px"
            allowClear
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">查询</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 表格 -->
    <a-table
      :columns="columns"
      :data-source="data"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      :scroll="{ x: 1400 }"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'result_id'">
          <a-button type="link" size="small" @click="goToQualityResult(record.result_id)">
            {{ record.result_id }}
          </a-button>
        </template>
        <template v-if="column.key === 'risk_type'">
          <a-tag :color="getRiskTypeColor(record.risk_type)">
            {{ record.risk_type || '-' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'priority'">
          <a-tag :color="getPriorityColor(record.priority)">
            {{ record.priority || '-' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'confirmed'">
          <template v-if="record.confirmed === null">-</template>
          <a-tag v-else :color="record.confirmed ? 'success' : 'default'">
            {{ record.confirmed ? '是' : '否' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'risk_level_comparison'">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-tag :color="getRiskColor(record.original_risk_level)">
              {{ getRiskText(record.original_risk_level) }}
            </a-tag>
            <span>→</span>
            <a-tag :color="getRiskColor(record.secondary_risk_level)">
              {{ getRiskText(record.secondary_risk_level) }}
            </a-tag>
          </div>
        </template>
        <template v-if="column.key === 'review_status'">
          <a-tag :color="getStatusColor(record.review_status)">
            {{ getStatusText(record.review_status) }}
          </a-tag>
        </template>
        <template v-if="column.key === 'completed_at'">
          {{ formatDateTime(record.completed_at) }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-button type="link" size="small" @click="showDetail(record)">详情</a-button>
        </template>
      </template>
    </a-table>

    <!-- 详情弹窗 -->
    <a-modal
      v-model:open="detailVisible"
      title="二次审查详情"
      width="900px"
      :footer="null"
      :closable="true"
    >
      <a-descriptions
        v-if="currentDetail"
        :column="2"
        bordered
        size="small"
        :label-style="{ width: '120px' }"
      >
        <!-- 审查基本信息 -->
        <a-descriptions-item label="审查ID">{{ currentDetail.id }}</a-descriptions-item>
        <a-descriptions-item label="质检结果ID">
          <a-button type="link" size="small" @click="goToQualityResult(currentDetail.result_id)">
            {{ currentDetail.result_id }}
          </a-button>
        </a-descriptions-item>

        <!-- 关联的销售/好友信息（来自详情API） -->
        <a-descriptions-item label="销售姓名">
          {{ currentDetail.quality_check_result?.user_name || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="好友姓名">
          {{ currentDetail.quality_check_result?.friend_name || '-' }}
        </a-descriptions-item>

        <!-- 风险等级对比 -->
        <a-descriptions-item label="原始风险等级">
          <a-tag :color="getRiskColor(currentDetail.original_risk_level)">
            {{ getRiskText(currentDetail.original_risk_level) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="二次风险等级">
          <a-tag :color="getRiskColor(currentDetail.secondary_risk_level)">
            {{ getRiskText(currentDetail.secondary_risk_level) }}
          </a-tag>
        </a-descriptions-item>

        <!-- 审查核心结果 -->
        <a-descriptions-item label="是否确认">
          <template v-if="currentDetail.confirmed === null">-</template>
          <a-tag v-else :color="currentDetail.confirmed ? 'success' : 'default'">
            {{ currentDetail.confirmed ? '是' : '否' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="风险类型">
          <a-tag :color="getRiskTypeColor(currentDetail.risk_type)">{{ currentDetail.risk_type || '-' }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="优先级">
          <a-tag :color="getPriorityColor(currentDetail.priority)">{{ currentDetail.priority || '-' }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="首次提出时间">{{ currentDetail.first_mention_time || '-' }}</a-descriptions-item>

        <!-- 状态与元数据 -->
        <a-descriptions-item label="审查状态">
          <a-tag :color="getStatusColor(currentDetail.review_status)">
            {{ getStatusText(currentDetail.review_status) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="审查模式">{{ currentDetail.review_mode || '-' }}</a-descriptions-item>
        <a-descriptions-item label="审查时间">{{ formatDateTime(currentDetail.completed_at) }}</a-descriptions-item>
        <a-descriptions-item label="批次ID">{{ currentDetail.batch_id || '-' }}</a-descriptions-item>
        <a-descriptions-item label="AI置信度">{{ currentDetail.confidence != null ? (currentDetail.confidence * 100).toFixed(1) + '%' : '-' }}</a-descriptions-item>
        <a-descriptions-item label="建议动作">{{ currentDetail.suggested_action || '-' }}</a-descriptions-item>

        <!-- 审查理由 -->
        <a-descriptions-item label="审查理由" :span="2">
          <pre style="white-space: pre-wrap; margin: 0; word-break: break-word;">{{ currentDetail.review_reason || '-' }}</pre>
        </a-descriptions-item>

        <!-- 错误信息 -->
        <a-descriptions-item v-if="currentDetail.error_msg" label="错误信息" :span="2">
          <pre style="white-space: pre-wrap; margin: 0; color: #ff4d4f;">{{ currentDetail.error_msg }}</pre>
        </a-descriptions-item>

        <!-- 关联质检结果信息 -->
        <a-descriptions-item label="质检结果详情" :span="2">
          <div v-if="currentDetail.quality_check_result" style="margin-top: 8px;">
            <a-descriptions :column="2" size="small" bordered>
              <a-descriptions-item label="风险等级">
                <a-tag :color="getRiskColor(currentDetail.quality_check_result.risk_level)">
                  {{ getRiskText(currentDetail.quality_check_result.risk_level) }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="触发方">{{ currentDetail.quality_check_result.trigger_party || '-' }}</a-descriptions-item>
              <a-descriptions-item label="风险类别">{{ currentDetail.quality_check_result.risk_category || '-' }}</a-descriptions-item>
              <a-descriptions-item label="处理状态">{{ currentDetail.quality_check_result.process_status || '-' }}</a-descriptions-item>
              <a-descriptions-item label="问题摘要" :span="2">
                <pre style="white-space: pre-wrap; margin: 0; word-break: break-word;">{{ currentDetail.quality_check_result.issue_summary || '-' }}</pre>
              </a-descriptions-item>
              <a-descriptions-item label="检测关键词" :span="2">{{ currentDetail.quality_check_result.detected_keywords || '-' }}</a-descriptions-item>
              <a-descriptions-item label="创建时间">{{ formatDateTime(currentDetail.quality_check_result.created_at) }}</a-descriptions-item>
            </a-descriptions>
          </div>
          <div v-else style="color: #999;">暂无关联的质检结果信息</div>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { getReviewList, getReviewDetail } from '@/api/qualityreview'

const router = useRouter()

// 状态
const loading = ref(false)
const data = ref([])
const detailVisible = ref(false)
const currentDetail = ref(null)

// 筛选条件（字段名与API query参数完全一致）
const filters = reactive({
  review_status: undefined,
  risk_type: undefined,
  priority: undefined,
  secondary_risk_level: undefined,
  confirmed: undefined,
  batch_id: ''
})

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  showSizeChanger: true,
  showTotal: (total) => `共 ${total} 条`,
  total: 0
})

// 表格列定义（dataIndex对应API返回的真实字段名）
const columns = [
  { title: '质检结果ID', key: 'result_id', dataIndex: 'result_id', width: 110 },
  { title: '销售姓名', dataIndex: 'user_name', key: 'user_name', width: 90 },
  { title: '好友姓名', dataIndex: 'friend_name', key: 'friend_name', width: 100 },
  { title: '是否确认', key: 'confirmed', dataIndex: 'confirmed', width: 85 },
  { title: '风险类型', key: 'risk_type', dataIndex: 'risk_type', width: 85 },
  { title: '优先级', key: 'priority', dataIndex: 'priority', width: 70 },
  { title: '风险等级对比', key: 'risk_level_comparison', width: 170 },
  { title: '审查状态', key: 'review_status', dataIndex: 'review_status', width: 90 },
  { title: '完成时间', key: 'completed_at', dataIndex: 'completed_at', width: 160 },
  { title: '操作', key: 'actions', width: 70, fixed: 'right' }
]

// 获取风险等级颜色
function getRiskColor(level) {
  const map = { high: 'error', medium: 'warning', low: 'blue', none: 'success', unknown: 'default' }
  return map[level] || 'default'
}

// 获取风险等级文本
function getRiskText(level) {
  const map = { high: '高风险', medium: '中风险', low: '低风险', none: '无风险', unknown: '未知' }
  return map[level] || level || '-'
}

// 获取审查状态颜色（对应数据库：pending/completed/failed）
function getStatusColor(status) {
  const map = { pending: 'default', completed: 'success', failed: 'error' }
  return map[status] || 'default'
}

// 获取审查状态文本
function getStatusText(status) {
  const map = { pending: '待审查', completed: '已完成', failed: '失败' }
  return map[status] || status || '-'
}

// 获取风险类型颜色
function getRiskTypeColor(type) {
  const map = { '退费': 'orange', '投诉': 'error', '其他': 'default' }
  return map[type] || 'default'
}

// 获取优先级颜色
function getPriorityColor(priority) {
  const map = { 'P0': 'error', 'P1': 'orange', 'P2': 'blue', 'P3': 'default' }
  return map[priority] || 'default'
}

// 格式化日期时间
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

// 获取列表数据
async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize
    }
    // 传入非空筛选条件（字段名与API query参数一致）
    if (filters.review_status) params.review_status = filters.review_status
    if (filters.risk_type) params.risk_type = filters.risk_type
    if (filters.priority) params.priority = filters.priority
    if (filters.secondary_risk_level) params.secondary_risk_level = filters.secondary_risk_level
    if (filters.confirmed !== undefined && filters.confirmed !== null) params.confirmed = filters.confirmed
    if (filters.batch_id) params.batch_id = filters.batch_id

    const res = await getReviewList(params)
    data.value = res.data || []
    pagination.total = res.total || 0
  } catch (error) {
    message.error('获取审查列表失败')
    data.value = []
  } finally {
    loading.value = false
  }
}

// 搜索
function handleSearch() {
  pagination.current = 1
  fetchData()
}

// 分页变化
function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  fetchData()
}

// 显示详情（通过详情API获取完整数据）
async function showDetail(record) {
  try {
    const res = await getReviewDetail(record.id)
    currentDetail.value = res || record
    detailVisible.value = true
  } catch (error) {
    message.error('获取详情失败')
    currentDetail.value = record
    detailVisible.value = true
  }
}

// 跳转到质检结果页面
function goToQualityResult(resultId) {
  router.push({ path: '/quality-results', query: { id: resultId } })
}

// 初始化
onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.quality-review {
  padding: 0;
}
</style>
