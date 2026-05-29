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
      <a-form-item label="合规状态">
        <a-select v-model:value="filters.is_compliant" placeholder="全部" style="width: 120px" allow-clear>
          <a-select-option value="compliant">合规</a-select-option>
          <a-select-option value="non_compliant">不合规</a-select-option>
        </a-select>
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
        <template v-if="column.key === 'is_compliant'">
          <a-tag :color="record.is_compliant === 'compliant' ? 'success' : 'error'">
            {{ record.is_compliant === 'compliant' ? '合规' : '不合规' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" @click="showDetail(record.id)">详情</a-button>
        </template>
      </template>
    </a-table>

    <!-- Detail modal -->
    <a-modal v-model:open="detailVisible" title="督学跟进合规详情" width="700px">
      <a-descriptions v-if="detailData" :column="2" bordered size="small">
        <a-descriptions-item label="销售ID">{{ detailData.user_id }}</a-descriptions-item>
        <a-descriptions-item label="好友ID">{{ detailData.friend_id }}</a-descriptions-item>
        <a-descriptions-item label="好友昵称">{{ detailData.friend_nick || '-' }}</a-descriptions-item>
        <a-descriptions-item label="合规状态">
          <a-tag :color="detailData.is_compliant === 'compliant' ? 'success' : 'error'">
            {{ detailData.is_compliant === 'compliant' ? '合规' : '不合规' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="跟进天数">{{ detailData.total_follow_up_days || '-' }}</a-descriptions-item>
        <a-descriptions-item label="聊天日期范围">{{ detailData.chat_date_range || '-' }}</a-descriptions-item>
        <a-descriptions-item label="窗口大小">{{ detailData.window_size_days || '-' }}天</a-descriptions-item>
        <a-descriptions-item label="最低要求次数">{{ detailData.min_required_count || '-' }}</a-descriptions-item>
        <a-descriptions-item label="实际最小次数">{{ detailData.min_window_count || '-' }}</a-descriptions-item>
        <a-descriptions-item label="创建时间">{{ formatTime(detailData.created_at) }}</a-descriptions-item>
      </a-descriptions>
      <div v-if="detailData?.violation_windows?.length" style="margin-top: 16px">
        <a-alert type="warning" show-icon message="存在违规窗口" style="margin-bottom: 12px" />
        <div v-for="(w, idx) in detailData.violation_windows" :key="idx" style="padding: 8px 12px; background: #fef2f2; border-radius: 6px; margin-bottom: 8px; font-size: 13px">
          <strong>窗口 {{ idx + 1 }}:</strong> {{ w.start || w.start_date }} ~ {{ w.end || w.end_date }}，
          次数: {{ w.count }}。
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getFollowUpList, getFollowUpDetail } from '@/api/followup'
import { formatTime } from '@/utils/format'

const data = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const detailData = ref(null)
const pagination = reactive({ current: 1, pageSize: 20, showSizeChanger: false, showTotal: (total) => `共 ${total} 条` })
const filters = reactive({ user_id: '', friend_id: '', is_compliant: '' })

const columns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }) => formatTime(text) },
  { title: '销售ID', dataIndex: 'user_id', key: 'user_id', width: 110 },
  { title: '好友昵称', dataIndex: 'friend_nick', key: 'friend_nick' },
  { title: '合规状态', key: 'is_compliant', width: 100 },
  { title: '跟进天数', dataIndex: 'total_follow_up_days', key: 'total_follow_up_days', width: 90 },
  { title: '聊天范围', dataIndex: 'chat_date_range', key: 'chat_date_range', width: 180, ellipsis: true },
  { title: '操作', key: 'actions', width: 80, fixed: 'right' },
]

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.friend_id) params.friend_id = filters.friend_id
    if (filters.is_compliant) params.is_compliant = filters.is_compliant
    const res = await getFollowUpList(params)
    data.value = res.data || []
    pagination.total = res.total || 0
  } catch {
    data.value = []
  } finally {
    loading.value = false
  }
}

function handleSearch() { pagination.current = 1; loadData() }
function handleReset() { filters.user_id = ''; filters.friend_id = ''; filters.is_compliant = ''; pagination.current = 1; loadData() }
function handleTableChange(pag) { pagination.current = pag.current; pagination.pageSize = pag.pageSize; loadData() }

async function showDetail(id) {
  detailData.value = await getFollowUpDetail(id)
  detailVisible.value = true
}

onMounted(loadData)
</script>
