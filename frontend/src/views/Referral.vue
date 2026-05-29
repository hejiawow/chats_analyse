<template>
  <div class="page-card">
    <!-- Filter bar -->
    <a-form layout="inline" :model="filters" style="margin-bottom: 16px">
      <a-form-item label="销售ID">
        <a-input v-model:value="filters.user_id" placeholder="销售ID" style="width: 140px" />
      </a-form-item>
      <a-form-item label="好友ID">
        <a-input v-model:value="filters.friend_id" placeholder="好友ID" style="width: 140px" />
      </a-form-item>
      <a-form-item>
        <a-button type="primary" @click="handleSearch">查询</a-button>
        <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
      </a-form-item>
    </a-form>

    <!-- Table -->
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
        <template v-if="column.key === 'status'">
          <a-tag v-if="record.status === 'failed'" color="error">失败</a-tag>
          <a-tag v-else-if="record.result?.status === '已发送'" color="success">已发送</a-tag>
          <a-tag v-else color="warning">未发送</a-tag>
        </template>
        <template v-if="column.key === 'evidence'">
          <span :title="getEvidence(record)">{{ getEvidence(record) }}</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" @click="showDetail(record.id)">详情</a-button>
        </template>
      </template>
    </a-table>

    <!-- Detail modal -->
    <a-modal v-model:open="detailVisible" title="转介绍详情" width="600px">
      <a-descriptions v-if="detailData" :column="1" bordered size="small">
        <a-descriptions-item label="销售ID">{{ detailData.user_id }}</a-descriptions-item>
        <a-descriptions-item label="好友ID">{{ detailData.friend_id }}</a-descriptions-item>
        <a-descriptions-item label="好友昵称">{{ detailData.friend_nick || '-' }}</a-descriptions-item>
        <a-descriptions-item label="状态">{{ detailData.status }}</a-descriptions-item>
        <a-descriptions-item label="创建时间">{{ formatTime(detailData.created_at) }}</a-descriptions-item>
        <a-descriptions-item label="发送状态">
          <a-tag :color="detailData.result?.status === '已发送' ? 'success' : 'warning'">
            {{ detailData.result?.status === '已发送' ? '已发送' : '未发送' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item v-if="detailData.result?.raw_response" label="证据原文">
          <pre style="white-space: pre-wrap; margin: 0; font-size: 13px">{{ getEvidence(detailData) }}</pre>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getReferralList, getReferralDetail } from '@/api/referral'
import { formatTime } from '@/utils/format'

const data = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const detailData = ref(null)
const pagination = reactive({ current: 1, pageSize: 20, showSizeChanger: false, showTotal: (total) => `共 ${total} 条` })
const filters = reactive({ user_id: '', friend_id: '' })

const columns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180, customRender: ({ text }) => formatTime(text) },
  { title: '销售ID', dataIndex: 'user_id', key: 'user_id', width: 120 },
  { title: '好友ID', dataIndex: 'friend_id', key: 'friend_id', width: 120 },
  { title: '好友昵称', dataIndex: 'friend_nick', key: 'friend_nick' },
  { title: '状态', key: 'status', width: 100 },
  { title: '检测结果', key: 'evidence', ellipsis: true },
  { title: '操作', key: 'actions', width: 80, fixed: 'right' },
]

function parseEvidenceFromRaw(raw) {
  if (!raw) return null
  const lines = raw.split('\n')
  const evidenceLines = []
  let inEvidenceSection = false

  for (const line of lines) {
    const stripped = line.trim()
    if (stripped.includes('【证据】')) {
      inEvidenceSection = true
      continue
    }
    if (inEvidenceSection) {
      if (stripped.startsWith('【') && !stripped.includes('证据')) {
        break
      }
      if (stripped && (stripped[0].match(/\d/) || stripped.startsWith('"') || stripped.startsWith("'"))) {
        evidenceLines.push(stripped)
      }
    }
  }
  return evidenceLines.length > 0 ? evidenceLines.join('\n') : null
}

function getEvidence(r) {
  if (r.status === 'failed') return r.error_msg || '未知错误'
  // 优先从 raw_response 解析证据
  const rawEvidence = parseEvidenceFromRaw(r.result?.raw_response)
  if (rawEvidence) return rawEvidence
  return r.result?.evidence || '-'
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.friend_id) params.friend_id = filters.friend_id
    const res = await getReferralList(params)
    data.value = res.data || []
    pagination.total = res.total || 0
  } catch {
    data.value = []
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.current = 1
  loadData()
}

function handleReset() {
  filters.user_id = ''
  filters.friend_id = ''
  pagination.current = 1
  loadData()
}

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

async function showDetail(id) {
  detailData.value = await getReferralDetail(id)
  detailVisible.value = true
}

onMounted(loadData)
</script>
