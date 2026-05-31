<template>
  <div class="page-card">
    <!-- 统计卡片 -->
    <div class="stats-row" style="margin-bottom: 16px">
      <a-card v-for="stat in stats" :key="stat.label" class="stat-card">
        <a-statistic :title="stat.label" :value="stat.count" :value-style="{ fontSize: '24px' }">
          <template #prefix>
            <component :is="stat.icon" />
          </template>
        </a-statistic>
      </a-card>
    </div>

    <!-- 筛选栏 -->
    <div style="margin-bottom: 16px">
      <a-form layout="inline" :model="filters">
        <a-form-item label="日志类型">
          <a-select v-model:value="filters.log_type" placeholder="全部" style="width: 120px" allow-clear>
            <a-select-option value="api_access">API访问</a-select-option>
            <a-select-option value="audit">审计日志</a-select-option>
            <a-select-option value="error">错误日志</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="日志级别">
          <a-select v-model:value="filters.log_level" placeholder="全部" style="width: 120px" allow-clear>
            <a-select-option value="info">信息</a-select-option>
            <a-select-option value="warning">警告</a-select-option>
            <a-select-option value="error">错误</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="用户名">
          <a-input v-model:value="filters.username" placeholder="用户名" style="width: 140px" allow-clear />
        </a-form-item>
        <a-form-item label="操作类型">
          <a-select v-model:value="filters.action" placeholder="全部" style="width: 140px" allow-clear>
            <a-select-option value="login">登录</a-select-option>
            <a-select-option value="login_failed">登录失败</a-select-option>
            <a-select-option value="logout">登出</a-select-option>
            <a-select-option value="trigger_analysis">触发分析</a-select-option>
            <a-select-option value="trigger_batch_quality_check">批量质检</a-select-option>
            <a-select-option value="cancel_task">取消任务</a-select-option>
            <a-select-option value="create_user">创建用户</a-select-option>
            <a-select-option value="update_user">更新用户</a-select-option>
            <a-select-option value="delete_user">删除用户</a-select-option>
            <a-select-option value="create_role">创建角色</a-select-option>
            <a-select-option value="update_role">更新角色</a-select-option>
            <a-select-option value="delete_role">删除角色</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="时间范围">
          <a-range-picker v-model:value="filters.timeRange" show-time format="YYYY-MM-DD HH:mm:ss" style="width: 340px" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
        </a-form-item>
      </a-form>
    </div>

    <!-- 日志表格 -->
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
        <template v-if="column.key === 'log_type'">
          <a-tag :color="getLogTypeColor(record.log_type)">{{ getLogTypeLabel(record.log_type) }}</a-tag>
        </template>
        <template v-if="column.key === 'log_level'">
          <a-tag :color="getLogLevelColor(record.log_level)">{{ getLogLevelLabel(record.log_level) }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <span v-if="record.action">{{ getActionLabel(record.action) }}</span>
          <span v-else style="color: #94a3b8">-</span>
        </template>
        <template v-if="column.key === 'request_info'">
          <div v-if="record.request_method">
            <a-tag :color="getMethodColor(record.request_method)">{{ record.request_method }}</a-tag>
            <span style="margin-left: 4px">{{ record.request_path }}</span>
            <span v-if="record.response_status" style="margin-left: 8px">
              <a-tag :color="record.response_status < 400 ? 'success' : 'error'">{{ record.response_status }}</a-tag>
              <span style="color: #666; margin-left: 4px">{{ record.response_time_ms }}ms</span>
            </span>
          </div>
          <span v-else style="color: #94a3b8">-</span>
        </template>
        <template v-if="column.key === 'error_info'">
          <div v-if="record.error_type">
            <a-tag color="error">{{ record.error_type }}</a-tag>
            <span style="color: #666; margin-left: 4px">{{ record.error_message?.slice(0, 50) }}...</span>
          </div>
          <span v-else style="color: #94a3b8">-</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" @click="showDetailModal(record)">详情</a-button>
        </template>
      </template>
    </a-table>

    <!-- 详情弹窗 -->
    <a-modal v-model:open="detailVisible" title="日志详情" width="700px" :footer="null">
      <a-descriptions :column="2" bordered size="small">
        <a-descriptions-item label="ID">{{ detailRecord.id }}</a-descriptions-item>
        <a-descriptions-item label="日志类型">{{ getLogTypeLabel(detailRecord.log_type) }}</a-descriptions-item>
        <a-descriptions-item label="日志级别">{{ detailRecord.log_level }}</a-descriptions-item>
        <a-descriptions-item label="创建时间">{{ detailRecord.created_at }}</a-descriptions-item>
        <a-descriptions-item label="用户ID">{{ detailRecord.user_id || '-' }}</a-descriptions-item>
        <a-descriptions-item label="用户名">{{ detailRecord.username || '-' }}</a-descriptions-item>
        <a-descriptions-item label="IP地址">{{ detailRecord.ip_address || '-' }}</a-descriptions-item>
        <a-descriptions-item label="User-Agent">{{ detailRecord.user_agent?.slice(0, 50) || '-' }}...</a-descriptions-item>
      </a-descriptions>

      <!-- API访问详情 -->
      <div v-if="detailRecord.log_type === 'api_access'" style="margin-top: 16px">
        <a-divider orientation="left">API请求信息</a-divider>
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="请求方法">{{ detailRecord.request_method }}</a-descriptions-item>
          <a-descriptions-item label="请求路径">{{ detailRecord.request_path }}</a-descriptions-item>
          <a-descriptions-item label="响应状态">{{ detailRecord.response_status }}</a-descriptions-item>
          <a-descriptions-item label="响应耗时">{{ detailRecord.response_time_ms }}ms</a-descriptions-item>
          <a-descriptions-item label="Query参数" :span="2">
            <pre style="margin: 0; white-space: pre-wrap; max-height: 100px; overflow: auto">{{ detailRecord.request_query || '-' }}</pre>
          </a-descriptions-item>
          <a-descriptions-item label="请求体" :span="2">
            <pre style="margin: 0; white-space: pre-wrap; max-height: 150px; overflow: auto">{{ formatJson(detailRecord.request_body) }}</pre>
          </a-descriptions-item>
        </a-descriptions>
      </div>

      <!-- 审计详情 -->
      <div v-if="detailRecord.log_type === 'audit'" style="margin-top: 16px">
        <a-divider orientation="left">审计信息</a-divider>
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="操作类型">{{ getActionLabel(detailRecord.action) }}</a-descriptions-item>
          <a-descriptions-item label="资源类型">{{ detailRecord.resource_type || '-' }}</a-descriptions-item>
          <a-descriptions-item label="资源ID">{{ detailRecord.resource_id || '-' }}</a-descriptions-item>
          <a-descriptions-item label="关联任务ID">{{ detailRecord.related_task_id || '-' }}</a-descriptions-item>
          <a-descriptions-item label="操作详情" :span="2">
            <pre style="margin: 0; white-space: pre-wrap; max-height: 150px; overflow: auto">{{ formatJson(detailRecord.action_detail) }}</pre>
          </a-descriptions-item>
        </a-descriptions>
      </div>

      <!-- 错误详情 -->
      <div v-if="detailRecord.log_type === 'error'" style="margin-top: 16px">
        <a-divider orientation="left">错误信息</a-divider>
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="错误类型">{{ detailRecord.error_type }}</a-descriptions-item>
          <a-descriptions-item label="错误消息">{{ detailRecord.error_message }}</a-descriptions-item>
          <a-descriptions-item label="堆栈跟踪">
            <pre style="margin: 0; white-space: pre-wrap; max-height: 300px; overflow: auto; font-size: 12px">{{ detailRecord.error_stacktrace }}</pre>
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </a-modal>

    <!-- 清理旧日志 -->
    <div style="margin-top: 16px; text-align: right">
      <a-popconfirm
        title="确定清理旧日志？"
        @confirm="handleDeleteOldLogs"
        ok-text="确定"
        cancel-text="取消"
      >
        <a-button danger>
          <template #icon><DeleteOutlined /></template>
          清理90天前的日志
        </a-button>
      </a-popconfirm>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, h } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApiOutlined,
  AuditOutlined,
  WarningOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import { getLogs, getLogStatistics, deleteOldLogs } from '@/api/logs'

// 统计数据
const stats = ref([
  { label: 'API访问', count: 0, icon: ApiOutlined },
  { label: '审计日志', count: 0, icon: AuditOutlined },
  { label: '错误日志', count: 0, icon: WarningOutlined },
])

// 筛选条件
const filters = reactive({
  log_type: undefined,
  log_level: undefined,
  username: undefined,
  action: undefined,
  timeRange: undefined,
})

// 表格数据
const data = ref([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 50,
  total: 0,
  showSizeChanger: true,
  showTotal: (total) => `共 ${total} 条`,
})

// 详情弹窗
const detailVisible = ref(false)
const detailRecord = ref({})

// 表格列
const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '类型', dataIndex: 'log_type', key: 'log_type', width: 100 },
  { title: '级别', dataIndex: 'log_level', key: 'log_level', width: 80 },
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '用户', dataIndex: 'username', key: 'username', width: 100 },
  { title: '操作', dataIndex: 'action', key: 'action', width: 140 },
  { title: '请求信息', key: 'request_info', width: 300 },
  { title: '错误信息', key: 'error_info', width: 200 },
  { title: 'IP', dataIndex: 'ip_address', key: 'ip_address', width: 120 },
  { title: '操作', key: 'actions', width: 80, fixed: 'right' },
]

// 加载统计数据
const loadStatistics = async () => {
  try {
    const res = await getLogStatistics({ group_by: 'log_type' })
    const statMap = {
      api_access: 0,
      audit: 1,
      error: 2,
    }
    res.data.forEach(item => {
      if (statMap[item.log_type] !== undefined) {
        stats.value[statMap[item.log_type]].count = item.count
      }
    })
  } catch (e) {
    console.error('Failed to load statistics:', e)
  }
}

// 加载日志列表
const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filters.log_type) params.log_type = filters.log_type
    if (filters.log_level) params.log_level = filters.log_level
    if (filters.username) params.username = filters.username
    if (filters.action) params.action = filters.action
    if (filters.timeRange && filters.timeRange[0]) {
      params.start_time = filters.timeRange[0].toISOString()
      params.end_time = filters.timeRange[1].toISOString()
    }

    const res = await getLogs(params)
    data.value = res.data
    pagination.total = res.total
  } catch (e) {
    console.error('Failed to load logs:', e)
  } finally {
    loading.value = false
  }
}

// 搜索和重置
const handleSearch = () => {
  pagination.current = 1
  loadData()
}

const handleReset = () => {
  filters.log_type = undefined
  filters.log_level = undefined
  filters.username = undefined
  filters.action = undefined
  filters.timeRange = undefined
  pagination.current = 1
  loadData()
}

// 分页变化
const handleTableChange = (pag) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

// 详情弹窗
const showDetailModal = (record) => {
  detailRecord.value = record
  detailVisible.value = true
}

// 清理旧日志
const handleDeleteOldLogs = async () => {
  try {
    const res = await deleteOldLogs(90)
    message.success(res.message)
    loadData()
    loadStatistics()
  } catch (e) {
    console.error('Failed to delete old logs:', e)
  }
}

// 工具函数
const getLogTypeColor = (type) => {
  const colors = { api_access: 'blue', audit: 'green', error: 'red' }
  return colors[type] || 'default'
}

const getLogTypeLabel = (type) => {
  const labels = { api_access: 'API访问', audit: '审计', error: '错误' }
  return labels[type] || type
}

const getLogLevelColor = (level) => {
  const colors = { info: 'blue', warning: 'orange', error: 'red', critical: 'red' }
  return colors[level] || 'default'
}

const getLogLevelLabel = (level) => {
  const labels = { info: '信息', warning: '警告', error: '错误', critical: '严重', debug: '调试' }
  return labels[level] || level
}

const getActionLabel = (action) => {
  const labels = {
    login: '登录',
    login_failed: '登录失败',
    logout: '登出',
    trigger_analysis: '触发分析',
    trigger_batch_quality_check: '批量质检',
    trigger_batch_quality_check_by_messages: '批量质检(消息)',
    cancel_task: '取消任务',
    create_user: '创建用户',
    update_user: '更新用户',
    delete_user: '删除用户',
    assign_roles: '分配角色',
    create_role: '创建角色',
    update_role: '更新角色',
    delete_role: '删除角色',
    create_keyword: '添加关键词',
    update_keyword: '更新关键词',
    delete_keyword: '删除关键词',
  }
  return labels[action] || action || '-'
}

const getMethodColor = (method) => {
  const colors = { GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red' }
  return colors[method] || 'default'
}

const formatJson = (str) => {
  if (!str) return '-'
  try {
    return JSON.stringify(JSON.parse(str), null, 2)
  } catch {
    return str
  }
}

// 初始化
onMounted(() => {
  loadData()
  loadStatistics()
})
</script>

<style scoped>
.stats-row {
  display: flex;
  gap: 16px;
}

.stat-card {
  flex: 1;
}

.page-card {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
}
</style>