<template>
  <div class="page-card quality-check-page">
    <!-- Info banner -->
    <div class="qc-info-banner">
      <div style="font-weight: 600; margin-bottom: 4px">批量质检分析</div>
      检测昨日至今日的聊天记录，识别投诉、退款、取消订单等风险关键词，AI深度分析风险等级和建议措施。
    </div>

    <!-- Form card -->
    <div class="qc-form-card">
      <div class="qc-batch-form">
        <div class="qc-form-row">
          <div class="qc-form-group">
            <div class="qc-form-label">质检方式</div>
            <a-radio-group v-model:value="batchForm.checkMode" button-style="solid">
              <a-radio-button value="by_pairs">按聊天对分析</a-radio-button>
              <a-radio-button value="by_messages">按聊天记录分析</a-radio-button>
            </a-radio-group>
          </div>
          <div class="qc-form-group">
            <div class="qc-form-label">时间范围</div>
            <a-range-picker
              v-model:value="batchForm.timeRange"
              :show-time="{ format: 'HH:mm:ss' }"
              format="YYYY-MM-DD HH:mm:ss"
              :placeholder="['开始时间', '结束时间']"
              style="width: 100%"
            />
          </div>
          <div class="qc-form-group">
            <div class="qc-form-label">销售ID（可选）</div>
            <a-input v-model:value="batchForm.user_id" placeholder="筛选特定销售（不填则分析全部）" style="width: 100%" />
          </div>
          <div class="qc-form-group">
            <div class="qc-form-label">分析数量上限</div>
            <a-input-number v-model:value="batchForm.limit" :min="1" :max="10000" placeholder="最大分析数量" style="width: 100%" />
          </div>
        </div>
        <div class="qc-batch-note">
          <template v-if="batchForm.checkMode === 'by_pairs'">
            批量质检将分析指定时间范围内有聊天记录的销售-好友对，仅记录检测到风险关键词的结果。
          </template>
          <template v-else>
            批量质检将先获取时间范围内所有聊天记录，进行关键词匹配后，仅对匹配到关键词的销售-好友对进行深度分析。
          </template>
          <br />
          <span style="color: #94a3b8">默认时间范围：昨天此时 至 今天此时（1天）</span>
        </div>
      </div>

      <!-- Submit -->
      <div class="qc-actions">
        <a-button type="primary" :loading="submitting" @click="handleBatchAnalyze" size="large">
          <template #icon><SafetyOutlined /></template>
          开始批量质检
        </a-button>
        <span v-if="errorMsg" class="error-msg">{{ errorMsg }}</span>
      </div>
    </div>

    <!-- Batch Progress -->
    <div v-if="batchProgress.total > 0" class="qc-batch-progress">
      <div class="qc-batch-progress-title">
        批量质检进度：{{ batchProgress.completed }} / {{ batchProgress.total }}
        <a-button
          v-if="batchProgress.status === 'running'"
          type="primary"
          danger
          size="small"
          :loading="cancelling"
          @click="handleCancelBatch"
          style="margin-left: 12px"
        >
          终止任务
        </a-button>
        <span v-if="batchProgress.status === 'cancelling'" class="qc-cancelling-tag">取消中...</span>
        <span v-if="batchProgress.status === 'cancelled'" class="qc-cancelled-tag">已取消</span>
      </div>
      <a-progress
        :percent="Math.round(batchProgress.completed / batchProgress.total * 100)"
        :status="batchProgress.status === 'completed' ? 'success' : batchProgress.status === 'cancelled' ? 'exception' : 'active'"
      />
      <div v-if="batchProgress.status === 'completed' || batchProgress.status === 'cancelled'" class="qc-batch-summary">
        <span class="qc-summary-item success">风险检测：{{ batchRiskCount }} 个</span>
        <span v-if="batchProgress.cancelled > 0" class="qc-summary-item warning">已取消：{{ batchProgress.cancelled }} 个</span>
        <span class="qc-summary-item error" @click="showBatchErrors">失败：{{ batchProgress.failed || 0 }} 个（点击查看详情）</span>
      </div>
    </div>

    
    <!-- Detail modal -->
    <a-modal v-model:open="detailVisible" title="质检详情" width="700px" okText="确定" cancelText="取消">
      <a-descriptions v-if="detailData" :column="1" bordered size="small">
        <a-descriptions-item label="销售ID">{{ detailData.user_id }}</a-descriptions-item>
        <a-descriptions-item label="好友ID">{{ detailData.friend_id }}</a-descriptions-item>
        <a-descriptions-item label="好友昵称">{{ detailData.friend_nick || '-' }}</a-descriptions-item>
        <a-descriptions-item label="好友备注">{{ detailData.chat_title || '-' }}</a-descriptions-item>
        <a-descriptions-item label="好友别名">{{ detailData.alias || '-' }}</a-descriptions-item>
        <a-descriptions-item label="绑定手机号">{{ detailData.phone || '-' }}</a-descriptions-item>
        <a-descriptions-item label="备注手机号">{{ detailData.remark_phone || '-' }}</a-descriptions-item>
        <a-descriptions-item label="检测时间">{{ detailData.check_time_start }} ~ {{ detailData.check_time_end }}</a-descriptions-item>
        <a-descriptions-item label="聊天记录数">{{ detailData.chat_record_count }}</a-descriptions-item>
        <a-descriptions-item label="关键词检测">
          <a-tag :color="detailData.keyword_detected === 'yes' ? 'error' : 'success'">
            {{ detailData.keyword_detected === 'yes' ? '检测到' : '未检测到' }}
          </a-tag>
          <span v-if="detailData.detected_keywords">（{{ detailData.detected_keywords }}）</span>
        </a-descriptions-item>
        <a-descriptions-item v-if="detailData.keyword_matches && detailData.keyword_matches.length" label="关键词匹配">
          <div v-for="(m, idx) in detailData.keyword_matches" :key="idx" style="margin-bottom: 8px">
            <div><strong>{{ m.keyword }}</strong> - {{ m.speaker}} - {{ m.time }}</div>
            <div style="color: #666">{{ m.message }}</div>
          </div>
          <a-button type="link" size="small" @click="showChatRecords" style="margin-top: 8px">查看全部聊天记录</a-button>
        </a-descriptions-item>
        <a-descriptions-item v-else label="聊天记录">
          <a-button type="link" size="small" @click="showChatRecords">查看全部聊天记录</a-button>
        </a-descriptions-item>
        <a-descriptions-item v-if="detailData.risk_level" label="风险等级">
          <span :class="['qc-risk-badge', detailData.risk_level]">{{ getRiskLevelText(detailData.risk_level) }}</span>
        </a-descriptions-item>
        <a-descriptions-item v-if="detailData.risk_category" label="风险类别">{{ detailData.risk_category }}</a-descriptions-item>
        <a-descriptions-item v-if="detailData.risk_description" label="风险描述">
          <pre style="white-space: pre-wrap; margin: 0">{{ detailData.risk_description }}</pre>
        </a-descriptions-item>
        <a-descriptions-item v-if="detailData.suggested_action" label="建议措施">
          <pre style="white-space: pre-wrap; margin: 0">{{ detailData.suggested_action }}</pre>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>

    <!-- 聊天记录弹窗 -->
    <a-modal v-model:open="chatRecordsVisible" title="全部聊天记录" width="800px" :footer="null" :closable="true">
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
            时间范围：{{ detailData.check_time_start }} ~ {{ detailData.check_time_end }}
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

    <!-- Batch errors modal -->
    <a-modal v-model:open="batchErrorsVisible" title="批量质检失败详情" width="600px" okText="关闭" :footer="null">
      <a-table
        :columns="batchErrorColumns"
        :data-source="batchErrors"
        :pagination="false"
        size="small"
        row-key="friend_id"
      />
      <template #footer>
        <a-button @click="batchErrorsVisible = false">关闭</a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { SafetyOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { getQualityCheckList, getQualityCheckDetail, triggerBatchQualityCheck, getBatchProgress, getBatchErrors, cancelBatchQualityCheck, triggerBatchQualityCheckByMessages, getQualityCheckChatRecords } from '@/api/qualitycheck'

const submitting = ref(false)
const errorMsg = ref('')
const cancelling = ref(false)

// Batch mode
const batchForm = reactive({
  checkMode: 'by_pairs', // 'by_pairs' 按聊天对分析，'by_messages' 按聊天记录分析
  timeRange: null,
  user_id: '',
  limit: 500,
})
const batchProgress = reactive({ completed: 0, total: 0, status: '', risk_detected: 0, no_chat: 0, failed: 0 })
const batchTaskId = ref('')
let batchPollInterval = null

// History
const history = ref([])
const historyLoading = ref(false)
const historyPagination = reactive({ current: 1, pageSize: 20, showSizeChanger: false, showTotal: (total) => `共 ${total} 条`, total: 0 })
const historyColumns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '销售ID', dataIndex: 'user_id', key: 'user_id', width: 120 },
  { title: '好友ID', dataIndex: 'friend_id', key: 'friend_id', width: 120 },
  { title: '关键词检测', key: 'keyword_detected', width: 100 },
  { title: '风险等级', key: 'risk_level', width: 100 },
  { title: '操作', key: 'actions', width: 80 },
]

// Detail
const detailVisible = ref(false)
const detailData = ref(null)

// 聊天记录弹窗
const chatRecordsVisible = ref(false)
const chatRecordsLoading = ref(false)
const chatRecordsData = ref([])
const chatRecordsTotal = ref(0)

// Batch errors
const batchErrorsVisible = ref(false)
const batchErrors = ref([])
const batchErrorColumns = [
  { title: '销售ID', dataIndex: 'user_id', key: 'user_id', width: 150 },
  { title: '好友ID', dataIndex: 'friend_id', key: 'friend_id', width: 120 },
  { title: '错误原因', dataIndex: 'error', key: 'error' },
]

function getRiskLevelText(level) {
  const map = { high: '高风险', medium: '中风险', low: '低风险', none: '无风险' }
  return map[level] || '未知'
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await getQualityCheckList({ page: historyPagination.current, page_size: historyPagination.pageSize })
    history.value = res.data || []
    historyPagination.total = res.total || 0
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

function handleTableChange(pag) {
  historyPagination.current = pag.current
  loadHistory()
}

async function viewDetail(record) {
  try {
    detailData.value = await getQualityCheckDetail(record.id)
    detailVisible.value = true
  } catch (err) {
    message.error('获取详情失败')
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

// === Batch mode functions ===

async function startBatchPolling(taskId) {
  batchPollInterval = setInterval(async () => {
    try {
      const progress = await getBatchProgress(taskId)
      batchProgress.completed = progress.completed || 0
      batchProgress.total = progress.total || 0
      batchProgress.status = progress.status || ''
      batchProgress.risk_detected = progress.risk_detected || 0
      batchProgress.no_chat = progress.no_chat || 0
      batchProgress.failed = progress.failed || 0
      batchProgress.cancelled = progress.cancelled || 0
      if (progress.status === 'completed' || progress.status === 'cancelled' || progress.status === 'no_sales' || progress.status === 'no_friends') {
        clearInterval(batchPollInterval)
        batchPollInterval = null
        submitting.value = false
        cancelling.value = false
        loadHistory()
      }
    } catch {
      // keep polling
    }
  }, 2000)
}

async function showBatchErrors() {
  if (!batchTaskId.value) return
  try {
    const res = await getBatchErrors(batchTaskId.value)
    batchErrors.value = res.errors || []
    batchErrorsVisible.value = true
  } catch {
    message.error('获取错误详情失败')
  }
}

async function handleBatchAnalyze() {
  errorMsg.value = ''
  batchProgress.completed = 0
  batchProgress.total = 0
  batchProgress.status = ''
  batchProgress.risk_detected = 0
  batchProgress.no_chat = 0
  batchProgress.failed = 0
  batchProgress.cancelled = 0

  submitting.value = true

  // 计算时间范围
  let startTime, endTime
  if (batchForm.timeRange && batchForm.timeRange.length === 2) {
    startTime = batchForm.timeRange[0].format('YYYY-MM-DD HH:mm:ss')
    endTime = batchForm.timeRange[1].format('YYYY-MM-DD HH:mm:ss')
  } else {
    // 默认昨天此时到今天此时
    const now = new Date()
    const yesterday = new Date(now - 24 * 60 * 60 * 1000)
    startTime = yesterday.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }).replace(/\//g, '-')
    endTime = now.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }).replace(/\//g, '-')
  }

  try {
    // 根据选择的质检方式调用不同的 API
    const apiFunc = batchForm.checkMode === 'by_messages'
      ? triggerBatchQualityCheckByMessages
      : triggerBatchQualityCheck

    const res = await apiFunc({
      start_time: startTime,
      end_time: endTime,
      user_id: batchForm.user_id || null,
      limit: batchForm.limit,
    })

    batchTaskId.value = res.task_id
    batchProgress.status = 'running'

    const successMsg = batchForm.checkMode === 'by_messages'
      ? '新批量质检已启动（基于聊天记录关键词匹配）'
      : '批量质检已启动'
    message.success(successMsg)
    startBatchPolling(res.task_id)

  } catch (err) {
    submitting.value = false
    errorMsg.value = err.message || '请求失败'
    message.warning(err.message || '请求失败')
  }
}

// Computed for batch summary
const batchRiskCount = computed(() => {
  return batchProgress.risk_detected || 0
})

// 取消批量质检任务
async function handleCancelBatch() {
  if (!batchTaskId.value) return
  cancelling.value = true
  try {
    await cancelBatchQualityCheck(batchTaskId.value)
    message.success('已发送终止请求，正在停止任务...')
    batchProgress.status = 'cancelling'
  } catch (err) {
    cancelling.value = false
    message.error('终止任务失败：' + (err.message || '未知错误'))
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.quality-check-page {
  width: 100%;
}

/* Info banner */
.qc-info-banner {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 24px;
  padding: 16px 20px;
  background: #fef2f2;
  border-radius: 12px;
  border-left: 3px solid #ef4444;
  line-height: 1.6;
}

/* Batch form */
.qc-batch-form {
  padding: 16px 0;
}

.qc-batch-form .qc-form-row {
  gap: 16px;
}

.qc-batch-note {
  margin-top: 12px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

/* Batch progress */
.qc-batch-progress {
  margin-top: 20px;
  padding: 16px 20px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
}

.qc-batch-progress-title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 12px;
}

.qc-batch-summary {
  margin-top: 12px;
  padding: 12px 16px;
  background: #ecfdf5;
  border-radius: 8px;
  font-size: 13px;
}

.qc-summary-item {
  margin-right: 20px;
}

.qc-summary-item.success {
  color: #16a34a;
}

.qc-summary-item.error {
  color: #ef4444;
  cursor: pointer;
}

.qc-summary-item.error:hover {
  text-decoration: underline;
}

.qc-summary-item.warning {
  color: #f59e0b;
}

.qc-cancelling-tag {
  margin-left: 12px;
  padding: 2px 8px;
  background: #fef3c7;
  color: #d97706;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.qc-cancelled-tag {
  margin-left: 12px;
  padding: 2px 8px;
  background: #fee2e2;
  color: #dc2626;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

/* Form card */
.qc-form-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.qc-form-row {
  display: flex;
  gap: 24px;
}

.qc-form-group {
  flex: 1;
}

.qc-form-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}

.qc-actions {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  align-items: center;
}

.error-msg {
  margin-left: 16px;
  color: #ef4444;
  font-size: 13px;
}

/* Risk badge */
.qc-risk-badge {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.qc-risk-badge.high {
  background: #fee2e2;
  color: #dc2626;
}

.qc-risk-badge.medium {
  background: #fef3c7;
  color: #d97706;
}

.qc-risk-badge.low {
  background: #dbeafe;
  color: #2563eb;
}

.qc-risk-badge.none {
  background: #dcfce7;
  color: #16a34a;
}

.qc-risk-badge.info {
  background: #e2e8f0;
  color: #64748b;
}

/* History section */
.qc-history-section {
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
}

/* 聊天记录弹窗样式 - 微信风格 */
.chat-records-list {
  max-height: 500px;
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
  max-height: 420px;
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
</style>