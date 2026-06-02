<template>
  <div>
    <!-- Stats cards -->
    <a-row :gutter="[16, 16]" style="margin-bottom: 24px">
      <a-col :span="5">
        <a-card :bordered="false" class="stat-card">
          <a-statistic title="今日分析" :value="stats.today_tasks || 0" :value-style="{ color: '#4f46e5' }">
            <template #prefix><ThunderboltOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="5">
        <a-card :bordered="false" class="stat-card">
          <a-statistic title="转介绍检测" :value="stats.referral_sent || 0" :value-style="{ color: '#10b981' }">
            <template #prefix><ShareAltOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="5">
        <a-card :bordered="false" class="stat-card">
          <a-statistic title="优秀话术" :value="stats.cases_found || 0" :value-style="{ color: '#f59e0b' }">
            <template #prefix><FileTextOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="5">
        <a-card :bordered="false" class="stat-card">
          <a-statistic title="成交案例" :value="stats.sj_count || 0" :value-style="{ color: '#8b5cf6' }">
            <template #prefix><TrophyOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card :bordered="false" class="stat-card">
          <a-statistic title="智能体数" :value="stats.active_agents || 0" :value-style="{ color: '#06b6d4' }">
            <template #prefix><RobotOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- Summary -->
    <a-card :bordered="false" style="margin-bottom: 24px">
      <a-descriptions size="small" :column="4">
        <a-descriptions-item label="转介绍">{{ stats.referral_sent || 0 }}</a-descriptions-item>
        <a-descriptions-item label="案例">{{ stats.cases_found || 0 }}</a-descriptions-item>
        <a-descriptions-item label="成交">{{ stats.sj_count || 0 }}</a-descriptions-item>
        <a-descriptions-item label="督学合规">{{ stats.fu_compliant || 0 }} 合规 / {{ stats.fu_non_compliant || 0 }} 不合规</a-descriptions-item>
      </a-descriptions>
    </a-card>

    <!-- Recent records (only shown with referral permission) -->
    <a-card v-if="authStore.hasPermission('read:referral')" :bordered="false" title="最近分析记录">
      <a-table
        :columns="columns"
        :data-source="recentData"
        :pagination="false"
        :loading="loading"
        size="small"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag v-if="record.status === 'failed'" color="error">失败</a-tag>
            <a-tag v-else-if="(record.result?.status) === '已发送'" color="success">已发送</a-tag>
            <a-tag v-else color="warning">未发送</a-tag>
          </template>
          <template v-if="column.key === 'actions'">
            <a-button size="small" @click="showDetail(record.id)">详情</a-button>
          </template>
        </template>
      </a-table>
      <div style="margin-top: 12px; text-align: right">
        <a-button type="link" @click="$router.push({ name: 'Referral' })">查看全部 →</a-button>
      </div>
    </a-card>

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
        <a-descriptions-item v-if="detailData.result?.evidence" label="证据原文">
          <pre style="white-space: pre-wrap; margin: 0; font-size: 13px">{{ detailData.result.evidence }}</pre>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getStats } from '@/api/stats'
import { getReferralList, getReferralDetail } from '@/api/referral'
import { formatTime } from '@/utils/format'
import { useAuthStore } from '@/store/auth'
import {
  ThunderboltOutlined,
  ShareAltOutlined,
  FileTextOutlined,
  TrophyOutlined,
  RobotOutlined,
} from '@ant-design/icons-vue'

const authStore = useAuthStore()
const stats = ref({})
const recentData = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const detailData = ref(null)

const columns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180, customRender: ({ text }) => formatTime(text) },
  { title: '销售ID', dataIndex: 'user_id', key: 'user_id' },
  { title: '好友昵称', dataIndex: 'friend_nick', key: 'friend_nick' },
  { title: '状态', key: 'status' },
  { title: '检测结果', dataIndex: 'result', key: 'result', ellipsis: true },
  { title: '操作', key: 'actions', width: 80 },
]

onMounted(async () => {
  try {
    stats.value = await getStats()
  } catch {}

  if (!authStore.hasPermission('read:referral')) return
  loading.value = true
  try {
    const data = await getReferralList({ page: 1, page_size: 5 })
    recentData.value = data.data || []
  } catch {
    recentData.value = []
  } finally {
    loading.value = false
  }
})

async function showDetail(id) {
  detailData.value = await getReferralDetail(id)
  detailVisible.value = true
}
</script>

<style scoped>
.stat-card :deep(.ant-statistic-title) {
  color: #64748b;
  font-size: 13px;
}
.stat-card :deep(.ant-statistic-content) {
  font-weight: 700;
}
.stat-card {
  border-top: 3px solid #4f46e5;
}
.stat-card:nth-child(2) { border-top-color: #10b981; }
.stat-card:nth-child(3) { border-top-color: #f59e0b; }
.stat-card:nth-child(4) { border-top-color: #8b5cf6; }
.stat-card:nth-child(5) { border-top-color: #06b6d4; }
</style>
