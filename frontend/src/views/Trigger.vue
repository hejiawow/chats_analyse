<template>
  <div class="page-card trigger-page">
    <!-- Info banner -->
    <div class="trigger-form-info">
      <div style="font-weight: 600; margin-bottom: 4px">触发分析</div>
      填写销售和客户信息，选择一个或多个智能体，提交后将自动从虎鲸 API 拉取聊天记录并执行 AI 分析。
    </div>

    <!-- Agent cards (horizontal) -->
    <div style="margin-bottom: 20px">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px">
        <span style="font-size: 14px; font-weight: 600">选择智能体</span>
        <div style="display: flex; gap: 8px">
          <a-button size="small" @click="selectAll">全选</a-button>
          <a-button size="small" @click="clearAll">清空</a-button>
        </div>
      </div>

      <div class="agent-cards">
        <div
          v-for="agent in agentOptions"
          :key="agent.value"
          class="agent-card"
          :class="{ 'agent-card-selected': isSelected(agent.value) }"
          @click="toggleAgent(agent.value)"
        >
          <div class="card-icon">
            <component :is="agent.icon" />
          </div>
          <div class="card-text">
            <div class="card-title">{{ agent.label }}</div>
            <div class="card-desc">{{ agent.desc }}</div>
          </div>
          <div class="card-check">
            <CheckCircleFilled v-if="isSelected(agent.value)" style="color: #4f46e5; font-size: 20px" />
            <span v-else class="unchecked-circle"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Form: Sales + Customer info -->
    <div class="info-form-card">
      <div class="info-form-row">
        <!-- Sales info -->
        <div class="info-form-group">
          <div class="info-form-label">销售信息</div>
          <div class="info-form-fields">
            <a-input v-model:value="form.user_id" placeholder="销售ID" class="field-input" />
            <a-input v-model:value="form.user_name" placeholder="销售姓名" class="field-input" />
          </div>
        </div>

        <!-- Customer info -->
        <div class="info-form-group">
          <div class="info-form-label">客户信息</div>
          <div class="info-form-fields">
            <a-input v-model:value="form.friend_id" placeholder="好友ID" class="field-input" />
            <a-input v-model:value="form.friend_phone" placeholder="客户手机号" class="field-input" />
            <a-input v-model:value="form.friend_wx_id" placeholder="客户微信号（选填）" class="field-input" />
            <a-input v-model:value="form.friend_alias" placeholder="客户别名（选填）" class="field-input" />
          </div>
        </div>
      </div>

      <!-- Submit -->
      <div class="info-form-actions">
        <a-button type="primary" :loading="submitting" @click="handleSubmit" size="large">
          <template #icon><ThunderboltOutlined /></template>
          开始分析
        </a-button>
        <span v-if="errorMsg" class="error-msg">{{ errorMsg }}</span>
      </div>
    </div>

    <!-- Progress + Logs -->
    <div v-if="isAnalyzing" class="trigger-progress">
      <div class="spinner"></div>
      <div class="trigger-progress-title">{{ progressTitle }}</div>
      <div class="trigger-progress-desc">{{ progressDesc }}</div>
    </div>

    <div v-if="isAnalyzing" class="trigger-logs-box">
      <div v-for="(log, idx) in logs" :key="idx" class="log-line">
        <span class="log-time">[{{ log.time }}]</span>
        <span :class="['log-msg', `log-${log.level}`]">{{ log.message }}</span>
      </div>
    </div>

    <!-- Result message -->
    <div v-if="resultMsg" :class="['trigger-result', 'show', resultType]">
      {{ resultMsg }}
    </div>

    <!-- History table -->
    <div class="history-section">
      <div style="font-size: 16px; font-weight: 600; margin-bottom: 12px">历史分析记录</div>
      <table v-if="history.length">
        <thead>
          <tr>
            <th>状态</th>
            <th>销售信息</th>
            <th>客户信息</th>
            <th>结果</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in history" :key="item.id">
            <td>
              <span class="badge" :class="item.status === 'success' ? 'badge-success' : 'badge-danger'">
                {{ item.status === 'success' ? '已完成' : '失败' }}
              </span>
            </td>
            <td><code>{{ item.saleInfo }}</code></td>
            <td>{{ item.friendInfo }}</td>
            <td style="max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="item.message">{{ item.message }}</td>
            <td>{{ item.time }}</td>
            <td><a-button size="small" type="link" @click="viewResult(item)">查看</a-button></td>
          </tr>
        </tbody>
      </table>
      <a-empty v-else description="暂无分析记录" :image="simpleImage" style="padding: 24px 0" />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Empty } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  ShareAltOutlined,
  FileTextOutlined,
  TrophyOutlined,
  CheckCircleOutlined,
  CheckCircleFilled,
} from '@ant-design/icons-vue'
import { triggerAll, triggerSingle, getLogs } from '@/api/trigger'
import { message } from 'ant-design-vue'

const router = useRouter()
const simpleImage = Empty.PRESENTED_IMAGE_SIMPLE

const submitting = ref(false)
const isAnalyzing = ref(false)
const progressTitle = ref('')
const progressDesc = ref('')
const logs = ref([])
const resultMsg = ref('')
const resultType = ref('')
const errorMsg = ref('')

const form = reactive({
  datasource: 'hujing',
  agents: ['referral', 'case', 'journey', 'follow_up'],
  user_name: '',
  user_id: '',
  friend_id: '',
  friend_phone: '',
  friend_wx_id: '',
  friend_alias: '',
})

const agentOptions = [
  { value: 'referral', label: '转介绍检测', icon: ShareAltOutlined, desc: '检测是否主动向客户推荐产品或服务' },
  { value: 'case', label: '优秀话术提取', icon: FileTextOutlined, desc: '提取优秀的销售话术和唤醒话术' },
  { value: 'journey', label: '优秀成交案例提取', icon: TrophyOutlined, desc: '分析成交案例，总结方法和策略' },
  { value: 'follow_up', label: '督学跟进合规检测', icon: CheckCircleOutlined, desc: '检测跟进频率，生成合规报告' },
]

function isSelected(value) {
  return form.agents.includes(value)
}

function toggleAgent(value) {
  const idx = form.agents.indexOf(value)
  if (idx >= 0) {
    form.agents.splice(idx, 1)
  } else {
    form.agents.push(value)
  }
  errorMsg.value = ''
}

function selectAll() {
  form.agents = ['referral', 'case', 'journey', 'follow_up']
}

function clearAll() {
  form.agents = []
}

// History
let historyIdCounter = 0
const history = reactive([])

function buildSaleInfo() {
  const parts = []
  if (form.user_name) parts.push(form.user_name)
  if (form.user_id) parts.push(form.user_id)
  return parts.join(' / ') || '-'
}

function buildFriendInfo() {
  const parts = []
  if (form.friend_id) parts.push(form.friend_id)
  if (form.friend_phone) parts.push(form.friend_phone)
  if (form.friend_wx_id) parts.push(form.friend_wx_id)
  if (form.friend_alias) parts.push(form.friend_alias)
  return parts.join(' / ') || '-'
}

let pollInterval = null

async function startPolling(taskId) {
  let lastCount = 0
  progressTitle.value = '正在分析中...'
  progressDesc.value = `销售: ${buildSaleInfo()} → 客户: ${buildFriendInfo()}`

  pollInterval = setInterval(async () => {
    try {
      const logData = await getLogs(taskId)
      if (logData.logs && logData.logs.length > lastCount) {
        const newLogs = logData.logs.slice(lastCount)
        logs.value.push(...newLogs)
        lastCount = logData.logs.length
        await nextTick()
        const logBox = document.querySelector('.trigger-logs-box')
        if (logBox) logBox.scrollTop = logBox.scrollHeight
      }
      if (logData.done) {
        clearInterval(pollInterval)
        pollInterval = null
      }
    } catch {
      // keep polling
    }
  }, 1000)
}

async function handleSubmit() {
  errorMsg.value = ''
  resultMsg.value = ''

  // Validation
  if (!form.user_name && !form.user_id) {
    errorMsg.value = '请填写销售姓名或销售ID（至少一个）'
    return
  }
  if (!form.friend_id && !form.friend_phone && !form.friend_wx_id && !form.friend_alias) {
    errorMsg.value = '请填写好友ID、客户手机号、客户微信号或客户别名（至少一个）'
    return
  }
  if (!form.agents.length) {
    errorMsg.value = '请选择一个智能体'
    return
  }

  submitting.value = true
  isAnalyzing.value = true
  logs.value = []
  progressTitle.value = ''
  progressDesc.value = '任务提交中...'

  const payload = {
    datasource: form.datasource,
    user_name: form.user_name,
    user_id: form.user_id,
    friend_id: form.friend_id ? parseInt(form.friend_id) : null,
    friend_phone: form.friend_phone,
    friend_wx_id: form.friend_wx_id,
    friend_alias: form.friend_alias,
    agent: form.agents.join(','),
  }

  const saleInfo = buildSaleInfo()
  const friendInfo = buildFriendInfo()

  try {
    const res = form.agents.length === 4
      ? await triggerAll(payload)
      : await triggerSingle(payload)

    const taskId = res.task_id

    startPolling(taskId)

    // Wait for polling to finish
    await new Promise((resolve) => {
      const check = setInterval(() => {
        if (pollInterval === null) {
          clearInterval(check)
          resolve()
        }
      }, 500)
    })

    const lastLog = logs.value[logs.value.length - 1]
    const isSuccess = lastLog && lastLog.level === 'success'
    const resultMessage = lastLog ? lastLog.message : '分析完成'

    isAnalyzing.value = false
    submitting.value = false

    if (isSuccess) {
      resultType.value = 'success'
      resultMsg.value = resultMessage
      message.success('分析完成')
    } else {
      resultType.value = 'error'
      resultMsg.value = resultMessage || '分析失败'
      message.error('分析任务失败')
    }

    // Add to history
    historyIdCounter++
    history.unshift({
      id: historyIdCounter,
      status: isSuccess ? 'success' : 'error',
      saleInfo,
      friendInfo,
      message: resultMessage,
      time: new Date().toLocaleString('zh-CN'),
    })

    // Reset form
    form.user_name = ''
    form.user_id = ''
    form.friend_id = ''
    form.friend_phone = ''
    form.friend_wx_id = ''
    form.friend_alias = ''
    form.agents = ['referral', 'case', 'journey', 'follow_up']
  } catch (err) {
    isAnalyzing.value = false
    submitting.value = false
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }

    const errMsg = err?.response?.data?.detail || err.message || '请求失败'
    resultType.value = 'error'
    resultMsg.value = errMsg
    message.error(errMsg)
  }
}

function viewResult() {
  router.push({ name: 'Referral' })
}
</script>

<style scoped>
.trigger-page {
  width: 100%;
}

/* Info banner */
.trigger-form-info {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 24px;
  padding: 16px 20px;
  background: #eef2ff;
  border-radius: 12px;
  border-left: 3px solid #4f46e5;
  line-height: 1.6;
}

/* Agent cards - horizontal layout */
.agent-cards {
  display: flex;
  gap: 12px;
}

.agent-card {
  flex: 1;
  min-width: 0;
  position: relative;
  display: flex;
  align-items: center;
  padding: 12px 14px;
  background: #ffffff;
  border: 1.5px solid #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 200ms ease;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  user-select: none;
}

.agent-card:hover {
  border-color: #818cf8;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.agent-card-selected {
  border-color: #4f46e5;
  background: #eef2ff;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 0 0 1px #4f46e5;
}

.card-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  background: #eef2ff;
  border-radius: 8px;
  flex-shrink: 0;
  color: #4f46e5;
}

.agent-card-selected .card-icon {
  background: #c7d2fe;
}

.card-text {
  flex: 1;
  margin-left: 10px;
  min-width: 0;
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-desc {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-check {
  flex-shrink: 0;
  margin-left: 10px;
}

.unchecked-circle {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 1.5px solid #d1d5db;
  border-radius: 50%;
}

/* Info form card */
.info-form-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.info-form-row {
  display: flex;
  gap: 24px;
}

.info-form-group {
  flex: 1;
}

.info-form-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}

.info-form-fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-input {
  width: 100%;
}

.info-form-actions {
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

/* Progress */
.trigger-progress {
  margin-top: 20px;
  padding: 12px 16px;
  border-radius: 8px;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  color: #4f46e5;
  display: flex;
  align-items: center;
  gap: 10px;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(79, 70, 229, 0.15);
  border-top-color: #4f46e5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.trigger-progress-title {
  font-size: 14px;
  font-weight: 600;
}

.trigger-progress-desc {
  font-size: 13px;
  opacity: 0.75;
}

/* Logs */
.trigger-logs-box {
  margin-top: 12px;
  background: #0f172a;
  border-radius: 8px;
  padding: 16px;
  font-family: "SF Mono", "Fira Code", "Cascadia Code", "Consolas", monospace;
  font-size: 13px;
  line-height: 1.7;
  max-height: 360px;
  overflow-y: auto;
  color: rgba(255, 255, 255, 0.6);
}

.trigger-logs-box::-webkit-scrollbar {
  width: 4px;
}

.trigger-logs-box::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}

.log-time {
  color: rgba(255, 255, 255, 0.3);
  margin-right: 6px;
  user-select: none;
}

.log-msg {
  color: rgba(255, 255, 255, 0.6);
}

.log-msg.log-error {
  color: #ef4444;
}

.log-msg.log-success {
  color: #10b981;
}

.log-msg.log-warning {
  color: #f59e0b;
}

.log-msg.log-info {
  color: rgba(255, 255, 255, 0.6);
}

/* Result */
.trigger-result {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  display: none;
}

.trigger-result.show {
  display: block;
}

.trigger-result.success {
  background: #ecfdf5;
  color: #059669;
  border: 1px solid #bbf7d0;
}

.trigger-result.error {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

/* History table */
.history-section {
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
}

.history-section table {
  width: 100%;
  border-collapse: collapse;
}

.history-section th {
  text-align: left;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  text-transform: uppercase;
}

.history-section td {
  padding: 12px 16px;
  font-size: 13px;
  border-bottom: 1px solid #e2e8f0;
  vertical-align: middle;
}

.history-section tr:last-child td {
  border-bottom: none;
}

.history-section tr:hover td {
  background: #f8fafc;
}

/* Badge */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.badge-success {
  background: #ecfdf5;
  color: #059669;
}

.badge-danger {
  background: #fef2f2;
  color: #dc2626;
}

.history-section code {
  font-size: 12px;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  color: #4f46e5;
}
</style>
