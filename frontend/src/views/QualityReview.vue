<template>
  <div class="quality-review">
    <!-- 筛选区 -->
    <a-card :bordered="false" style="margin-bottom: 16px">
      <a-form layout="inline" :model="filters">
        <a-form-item label="审查状态">
          <a-select v-model:value="filters.review_status" placeholder="全部" style="width: 120px" allowClear>
            <a-select-option value="completed">已完成</a-select-option>
            <a-select-option value="failed">失败</a-select-option>
            <a-select-option value="pending">待审查</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="风险类型">
          <a-select v-model:value="filters.risk_types" mode="multiple" placeholder="全部" style="width: 200px" allowClear :maxTagCount="2">
            <a-select-option value="退费">退费</a-select-option>
            <a-select-option value="投诉">投诉</a-select-option>
            <a-select-option value="其他">其他</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="优先级">
          <a-select v-model:value="filters.priorities" mode="multiple" placeholder="全部" style="width: 200px" allowClear :maxTagCount="2">
            <a-select-option value="P0">P0</a-select-option>
            <a-select-option value="P1">P1</a-select-option>
            <a-select-option value="P2">P2</a-select-option>
            <a-select-option value="P3">P3</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="二次风险等级">
          <a-select v-model:value="filters.secondary_risk_levels" mode="multiple" placeholder="全部" style="width: 260px" allowClear :maxTagCount="2">
            <a-select-option value="high">高风险</a-select-option>
            <a-select-option value="medium">中风险</a-select-option>
            <a-select-option value="low">低风险</a-select-option>
            <a-select-option value="none">无风险</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="是否属退费投诉">
          <a-select v-model:value="filters.confirmed" placeholder="全部" style="width: 90px" allowClear>
            <a-select-option :value="true">是</a-select-option>
            <a-select-option :value="false">否</a-select-option>
          </a-select>
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
      :scroll="{ x: 1600 }"
      size="small"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'result_id'">
          <a-button type="link" size="small" @click="goToQualityResult(record.result_id)">{{ record.result_id }}</a-button>
        </template>
        <template v-if="column.key === 'risk_category'">
          <a-tag v-if="record.risk_category" color="blue">{{ record.risk_category }}</a-tag>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'risk_type'">
          <a-tag :color="getRiskTypeColor(record.risk_type)">{{ record.risk_type || '-' }}</a-tag>
        </template>
        <template v-if="column.key === 'priority'">
          <a-tag :color="getPriorityColor(record.priority)">{{ record.priority || '-' }}</a-tag>
        </template>
        <template v-if="column.key === 'confirmed'">
          <template v-if="record.confirmed === null || record.confirmed === undefined">-</template>
          <a-tag v-else :color="record.confirmed ? 'success' : 'default'">{{ record.confirmed ? '是' : '否' }}</a-tag>
        </template>
        <template v-if="column.key === 'risk_level_comparison'">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-tag :color="getRiskColor(record.original_risk_level)">{{ getRiskText(record.original_risk_level) }}</a-tag>
            <span>→</span>
            <a-tag :color="getRiskColor(record.secondary_risk_level)">{{ getRiskText(record.secondary_risk_level) }}</a-tag>
          </div>
        </template>
        <template v-if="column.key === 'review_status'">
          <a-tag :color="getStatusColor(record.review_status)">{{ getStatusText(record.review_status) }}</a-tag>
        </template>
        <template v-if="column.key === 'completed_at'">{{ formatDateTime(record.completed_at) }}</template>
        <template v-if="column.key === 'retry_count'">
          <span v-if="record.retry_count">{{ record.retry_count }}</span>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button type="link" size="small" @click="showDetail(record)">详情</a-button>
        </template>
      </template>
    </a-table>

    <!-- 详情弹窗：左右两栏 -->
    <a-modal v-model:open="detailVisible" title="二次审查详情" width="1100px" :footer="null" :closable="true" style="top: 20px">
      <div v-if="currentDetail" class="review-detail-layout">
        <!-- 左栏：第一次质检结果 -->
        <div class="review-col review-col-left">
          <div class="col-title">第一次质检结果</div>
          <a-descriptions :column="1" size="small" bordered :label-style="{ width: '100px', minWidth: '100px' }">
            <a-descriptions-item label="销售">{{ currentDetail.quality_check_result?.user_name || '-' }} ({{ currentDetail.quality_check_result?.user_id || '-' }})</a-descriptions-item>
            <a-descriptions-item label="好友">{{ currentDetail.quality_check_result?.friend_name || '-' }} ({{ currentDetail.quality_check_result?.friend_id || '-' }})</a-descriptions-item>
            <a-descriptions-item label="好友备注">{{ currentDetail.quality_check_result?.chat_title || '-' }}</a-descriptions-item>
            <a-descriptions-item label="风险等级">
              <a-tag :color="getRiskColor(currentDetail.quality_check_result?.modified_risk_level || currentDetail.quality_check_result?.risk_level)">
                {{ getRiskText(currentDetail.quality_check_result?.modified_risk_level || currentDetail.quality_check_result?.risk_level) }}
              </a-tag>
              <a-tag v-if="currentDetail.quality_check_result?.modified_risk_level" color="purple" size="small" style="margin-left: 4px">已修正</a-tag>
            </a-descriptions-item>
            <!-- <a-descriptions-item label="原始风险等级">
              <a-tag :color="getRiskColor(currentDetail.quality_check_result?.risk_level)">{{ getRiskText(currentDetail.quality_check_result?.risk_level) }}</a-tag>
            </a-descriptions-item> -->
            <a-descriptions-item label="风险类型">{{ currentDetail.quality_check_result?.risk_category || '-' }}</a-descriptions-item>
            <a-descriptions-item label="触发方">{{ getTriggerPartyText(currentDetail.quality_check_result?.trigger_party) }}</a-descriptions-item>
            <a-descriptions-item label="优先级">
              <a-tag :color="getPriorityColor(currentDetail.quality_check_result?.action_priority)">{{ currentDetail.quality_check_result?.action_priority || '-' }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="建议动作">{{ currentDetail.quality_check_result?.action_type || '-' }}</a-descriptions-item>
            <a-descriptions-item label="责任方">{{ currentDetail.quality_check_result?.recommended_owner || '-' }}</a-descriptions-item>
            <a-descriptions-item label="检测关键词">{{ currentDetail.quality_check_result?.detected_keywords || '-' }}</a-descriptions-item>
            <a-descriptions-item label="问题摘要">
              <pre class="pre-wrap">{{ currentDetail.quality_check_result?.issue_summary || '-' }}</pre>
            </a-descriptions-item>
            <a-descriptions-item label="关键证据" v-if="currentDetail.quality_check_result?.key_evidence?.length">
              <div v-for="(e, idx) in currentDetail.quality_check_result.key_evidence" :key="idx" class="evidence-item">
                <div class="evidence-meta">{{ e.speaker || '-' }} · {{ e.time || '-' }}</div>
                <div class="evidence-content">{{ e.content || '-' }}</div>
              </div>
            </a-descriptions-item>
            <a-descriptions-item label="检测时间">{{ formatDateTime(currentDetail.quality_check_result?.created_at) }}</a-descriptions-item>
          </a-descriptions>
          <div style="margin-top: 12px">
            <a-button type="primary" ghost @click="showChatRecords">查看全部聊天记录</a-button>
          </div>
        </div>

        <!-- 右栏：二次审查结果 -->
        <div class="review-col review-col-right">
          <div class="col-title">
            二次审查结果
            <div class="col-title-actions">
              <a-button v-if="!editMode" type="primary" size="small" @click="enterEdit">编辑</a-button>
              <template v-else>
                <a-button size="small" @click="cancelEdit">取消</a-button>
                <a-button type="primary" size="small" :loading="editLoading" @click="saveEdit" style="margin-left: 8px">保存</a-button>
              </template>
            </div>
          </div>
          <!-- 非编辑模式 -->
          <a-descriptions v-if="!editMode" :column="1" size="small" bordered :label-style="{ width: '100px', minWidth: '100px' }">
            <a-descriptions-item label="审查状态">
              <a-tag :color="getStatusColor(currentDetail.review_status)">{{ getStatusText(currentDetail.review_status) }}</a-tag>
              <span v-if="currentDetail.retry_count" style="margin-left: 8px; color: #999; font-size: 12px">重试 {{ currentDetail.retry_count }} 次</span>
            </a-descriptions-item>
            <a-descriptions-item label="是否确认">
              <template v-if="currentDetail.confirmed === null || currentDetail.confirmed === undefined">-</template>
              <a-tag v-else :color="currentDetail.confirmed ? 'success' : 'default'">{{ currentDetail.confirmed ? '是' : '否' }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="风险类型">
              <a-tag :color="getRiskTypeColor(currentDetail.risk_type)">{{ currentDetail.risk_type || '-' }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="二次风险等级">
              <a-tag :color="getRiskColor(currentDetail.secondary_risk_level)">{{ getRiskText(currentDetail.secondary_risk_level) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="优先级">
              <a-tag :color="getPriorityColor(currentDetail.priority)">{{ currentDetail.priority || '-' }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="首次提出时间">{{ currentDetail.first_mention_time || '-' }}</a-descriptions-item>
            <a-descriptions-item label="建议动作">{{ currentDetail.suggested_action || '-' }}</a-descriptions-item>
            <a-descriptions-item label="AI置信度">{{ currentDetail.confidence != null ? (currentDetail.confidence * 100).toFixed(1) + '%' : '-' }}</a-descriptions-item>
            <!-- <a-descriptions-item label="审查模式">{{ currentDetail.review_mode || '-' }}</a-descriptions-item> -->
            <a-descriptions-item label="审查时间">{{ formatDateTime(currentDetail.completed_at) }}</a-descriptions-item>
            <a-descriptions-item label="审查理由">
              <pre class="pre-wrap">{{ currentDetail.review_reason || '-' }}</pre>
            </a-descriptions-item>
            <a-descriptions-item v-if="currentDetail.error_msg" label="错误信息">
              <pre class="pre-wrap" style="color: #ff4d4f;">{{ currentDetail.error_msg }}</pre>
            </a-descriptions-item>
          </a-descriptions>
          <!-- 编辑模式 -->
          <div v-else class="edit-form">
            <a-form :label-col="{ style: { width: '100px' } }" size="small">
              <a-form-item label="是否确认">
                <a-select v-model:value="editForm.confirmed" placeholder="请选择">
                  <a-select-option :value="true">是</a-select-option>
                  <a-select-option :value="false">否</a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item label="风险类型">
                <a-select v-model:value="editForm.risk_type">
                  <a-select-option value="退费">退费</a-select-option>
                  <a-select-option value="投诉">投诉</a-select-option>
                  <a-select-option value="其他">其他</a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item label="二次风险等级">
                <a-select v-model:value="editForm.secondary_risk_level">
                  <a-select-option value="high">高风险</a-select-option>
                  <a-select-option value="medium">中风险</a-select-option>
                  <a-select-option value="low">低风险</a-select-option>
                  <a-select-option value="none">无风险</a-select-option>
                  <a-select-option value="unknown">未知</a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item label="优先级">
                <a-select v-model:value="editForm.priority">
                  <a-select-option value="P0">P0 立即</a-select-option>
                  <a-select-option value="P1">P1 今日</a-select-option>
                  <a-select-option value="P2">P2 复核</a-select-option>
                  <a-select-option value="P3">P3 观察</a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item label="首次提出时间">
                <a-input v-model:value="editForm.first_mention_time" placeholder="如 2026-06-01 14:30" />
              </a-form-item>
              <a-form-item label="建议动作">
                <a-select v-model:value="editForm.suggested_action">
                  <a-select-option value="立即介入">立即介入</a-select-option>
                  <a-select-option value="主管复核">主管复核</a-select-option>
                  <a-select-option value="客服跟进">客服跟进</a-select-option>
                  <a-select-option value="销售安抚">销售安抚</a-select-option>
                  <a-select-option value="培训复盘">培训复盘</a-select-option>
                  <a-select-option value="误报观察">误报观察</a-select-option>
                  <a-select-option value="无需处理">无需处理</a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item label="审查理由">
                <a-textarea v-model:value="editForm.review_reason" :rows="4" placeholder="请输入审查理由" />
              </a-form-item>
            </a-form>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 聊天记录弹窗 -->
    <a-modal v-model:open="chatVisible" title="全部聊天记录" width="850px" :footer="null" style="top: 20px">
      <div v-if="chatLoading" style="text-align: center; padding: 40px"><a-spin /></div>
      <div v-else-if="chatData.length === 0" style="text-align: center; padding: 40px; color: #999">暂无聊天记录</div>
      <div v-else class="chat-records-list">
        <div class="chat-records-header">
          共 {{ chatData.length }} 条聊天记录
          <span v-if="chatTimeRange" style="margin-left: 12px; color: #666">
            {{ formatDateTime(chatTimeRange.start) }} ~ {{ formatDateTime(chatTimeRange.end) }}
          </span>
        </div>
        <div class="chat-records-content">
          <div v-for="(msg, idx) in chatData" :key="idx" class="chat-message" :class="{ 'is-self': msg.author === 'right' }">
            <div class="chat-message-time" v-if="shouldShowTime(idx)">{{ msg.createTime }}</div>
            <div class="chat-message-row">
              <div class="chat-avatar" :class="{ 'self-avatar': msg.author === 'right' }">{{ msg.author === 'right' ? '销' : '客' }}</div>
              <div class="chat-bubble"><div class="chat-bubble-content">{{ msg.sentence }}</div></div>
            </div>
          </div>
        </div>
      </div>
      <template #footer><a-button @click="chatVisible = false">关闭</a-button></template>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { getReviewList, getReviewDetail, updateReviewDetail, getReviewChatRecords } from '@/api/qualityreview'

const router = useRouter()

const loading = ref(false)
const data = ref([])
const detailVisible = ref(false)
const currentDetail = ref(null)
const editMode = ref(false)
const editLoading = ref(false)
const editForm = reactive({
  confirmed: undefined,
  risk_type: undefined,
  secondary_risk_level: undefined,
  priority: undefined,
  first_mention_time: '',
  suggested_action: undefined,
  review_reason: ''
})

// 聊天记录
const chatVisible = ref(false)
const chatLoading = ref(false)
const chatData = ref([])
const chatTimeRange = ref(null)

const filters = reactive({
  review_status: undefined,
  risk_types: [],
  priorities: [],
  secondary_risk_levels: [],
  confirmed: true,
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  showSizeChanger: true,
  showTotal: (total) => `共 ${total} 条`,
  total: 0
})

const columns = [
  { title: '质检ID', key: 'result_id', dataIndex: 'result_id', width: 80 },
  { title: '销售姓名', dataIndex: 'user_name', key: 'user_name', width: 90 },
  { title: '好友姓名', dataIndex: 'friend_name', key: 'friend_name', width: 100 },
  { title: '是否属退费投诉', key: 'confirmed', width: 110 },
  { title: '初次质检风险', key: 'risk_category', width: 110 },
  { title: '二次判定风险', key: 'risk_type', width: 100 },
  { title: '优先级', key: 'priority', width: 70 },
  { title: '风险等级对比', key: 'risk_level_comparison', width: 170 },
  { title: '审查状态', key: 'review_status', width: 90 },
  { title: '重试', key: 'retry_count', width: 60 },
  { title: '完成时间', key: 'completed_at', width: 160 },
  { title: '操作', key: 'actions', width: 70, fixed: 'right' }
]

function getRiskColor(level) {
  return { high: 'error', medium: 'warning', low: 'blue', none: 'success', unknown: 'default' }[level] || 'default'
}
function getRiskText(level) {
  return { high: '高风险', medium: '中风险', low: '低风险', none: '无风险', unknown: '未知' }[level] || level || '-'
}
function getStatusColor(s) { return { pending: 'default', completed: 'success', failed: 'error' }[s] || 'default' }
function getStatusText(s) { return { pending: '待审查', completed: '已完成', failed: '失败' }[s] || s || '-' }
function getRiskTypeColor(t) { return { '退费': 'orange', '投诉': 'error', '其他': 'default' }[t] || 'default' }
function getPriorityColor(p) { return { P0: 'error', P1: 'orange', P2: 'blue', P3: 'default' }[p] || 'default' }
function getTriggerPartyText(t) { return { sales: '销售', customer: '客户', both: '双方' }[t] || t || '-' }

function formatDateTime(iso) {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
  } catch { return iso }
}

// 聊天记录时间显示
function shouldShowTime(idx) {
  if (idx === 0) return true
  const prev = chatData.value[idx - 1]?.createTime
  const curr = chatData.value[idx]?.createTime
  if (!prev || !curr) return false
  return (new Date(curr) - new Date(prev)) / 60000 >= 5
}

async function fetchData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (filters.review_status) params.review_status = filters.review_status
    if (filters.risk_types && filters.risk_types.length) params.risk_type = filters.risk_types.join(',')
    if (filters.priorities && filters.priorities.length) params.priority = filters.priorities.join(',')
    if (filters.secondary_risk_levels && filters.secondary_risk_levels.length) params.secondary_risk_level = filters.secondary_risk_levels.join(',')
    if (filters.confirmed !== undefined && filters.confirmed !== null) params.confirmed = filters.confirmed
    const res = await getReviewList(params)
    data.value = res.data || []
    pagination.total = res.total || 0
  } catch { data.value = [] }
  finally { loading.value = false }
}

function handleSearch() { pagination.current = 1; fetchData() }
function handleTableChange(pag) { pagination.current = pag.current; pagination.pageSize = pag.pageSize; fetchData() }

async function showDetail(record) {
  try {
    const res = await getReviewDetail(record.id)
    currentDetail.value = res || record
  } catch { currentDetail.value = record }
  editMode.value = false
  detailVisible.value = true
}

function enterEdit() {
  const d = currentDetail.value
  editForm.confirmed = d.confirmed
  editForm.risk_type = d.risk_type
  editForm.secondary_risk_level = d.secondary_risk_level
  editForm.priority = d.priority
  editForm.first_mention_time = d.first_mention_time || ''
  editForm.suggested_action = d.suggested_action
  editForm.review_reason = d.review_reason || ''
  editMode.value = true
}

function cancelEdit() { editMode.value = false }

async function saveEdit() {
  editLoading.value = true
  try {
    const res = await updateReviewDetail(currentDetail.value.id, {
      confirmed: editForm.confirmed,
      risk_type: editForm.risk_type,
      secondary_risk_level: editForm.secondary_risk_level,
      priority: editForm.priority,
      first_mention_time: editForm.first_mention_time || null,
      suggested_action: editForm.suggested_action,
      review_reason: editForm.review_reason,
    })
    // 更新详情数据
    Object.assign(currentDetail.value, res)
    editMode.value = false
    message.success('保存成功')
    fetchData()
  } catch { message.error('保存失败') }
  finally { editLoading.value = false }
}

async function showChatRecords() {
  const resultId = currentDetail.value?.result_id
  if (!resultId) return
  chatVisible.value = true
  chatLoading.value = true
  chatData.value = []
  chatTimeRange.value = null
  try {
    const res = await getReviewChatRecords(resultId)
    chatData.value = res.data || []
    chatTimeRange.value = res.time_range || null
  } catch { chatData.value = [] }
  finally { chatLoading.value = false }
}

function goToQualityResult(resultId) {
  router.push({ path: '/quality-results', query: { id: resultId } })
}

onMounted(() => { fetchData() })
</script>

<style scoped>
.quality-review { padding: 0; }

.review-detail-layout {
  display: flex;
  gap: 20px;
}
.review-col {
  flex: 1;
  min-width: 0;
}
.review-col-left {
  border-right: 1px solid #f0f0f0;
  padding-right: 20px;
}
.col-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #1890ff;
  color: #1890ff;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.review-col-right .col-title {
  border-bottom-color: #52c41a;
  color: #52c41a;
}
.col-title-actions {
  display: flex;
  gap: 4px;
}

.pre-wrap {
  white-space: pre-wrap;
  margin: 0;
  word-break: break-word;
}

.evidence-item {
  padding: 6px 8px;
  margin-bottom: 6px;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  background: #fafafa;
}
.evidence-meta {
  font-size: 12px;
  color: #999;
  margin-bottom: 2px;
}
.evidence-content {
  color: #333;
  line-height: 1.5;
}

.edit-form {
  padding: 0 4px;
}

/* 聊天记录样式 */
.chat-records-list { max-height: 800px; }
.chat-records-header {
  padding: 10px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
  color: #334155;
}
.chat-records-content {
  padding: 16px;
  max-height: 700px;
  overflow-y: auto;
  background: #ededed;
}
.chat-message { margin-bottom: 12px; }
.chat-message-time { text-align: center; font-size: 12px; color: #999; margin-bottom: 8px; }
.chat-message-row { display: flex; align-items: flex-start; }
.chat-message.is-self .chat-message-row { flex-direction: row-reverse; }
.chat-avatar {
  width: 36px; height: 36px; border-radius: 4px; background: #e0e0e0;
  display: flex; align-items: center; justify-content: center; font-size: 14px; color: #666; flex-shrink: 0;
}
.chat-avatar.self-avatar { background: #07c160; color: #fff; }
.chat-bubble { max-width: 70%; margin: 0 10px; position: relative; }
.chat-bubble-content {
  padding: 10px 14px; background: #fff; border-radius: 4px;
  font-size: 14px; color: #333; line-height: 1.5; word-break: break-word;
  box-shadow: 0 1px 1px rgba(0,0,0,0.1);
}
.chat-message.is-self .chat-bubble-content { background: #95ec69; }
</style>
