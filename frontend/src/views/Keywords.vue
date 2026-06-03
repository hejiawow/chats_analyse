<template>
  <div class="page-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">关键词管理</h3>
      <a-button type="primary" @click="showCreateModal">
        <template #icon><PlusOutlined /></template>
        新增关键词
      </a-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-section">
      <div class="stats-cards">
        <div class="stat-card stat-card-total">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">关键词总数</div>
        </div>
        <div class="stat-card stat-card-active">
          <div class="stat-value">{{ stats.active_count }}</div>
          <div class="stat-label">已启用</div>
        </div>
        <div class="stat-card stat-card-inactive">
          <div class="stat-value">{{ stats.inactive_count }}</div>
          <div class="stat-label">已禁用</div>
        </div>
      </div>

      <!-- 按类别统计 -->
      <div class="stats-detail">
        <div class="stats-group">
          <div class="stats-group-title">按类别分布</div>
          <div class="stats-bars">
            <div v-for="item in stats.category_stats" :key="item.category" class="stats-bar-item">
              <span class="bar-label">{{ categoryLabels[item.category] || item.category }}</span>
              <div class="bar-container">
                <div
                  class="bar-fill"
                  :style="{
                    width: (item.count / stats.total * 100) + '%',
                    backgroundColor: categoryColors[item.category] || '#1890ff'
                  }"
                ></div>
              </div>
              <span class="bar-count">{{ item.count }}</span>
            </div>
          </div>
        </div>

        <!-- 按严重程度统计 -->
        <div class="stats-group">
          <div class="stats-group-title">按严重程度分布</div>
          <div class="stats-bars">
            <div v-for="item in stats.severity_stats" :key="item.severity" class="stats-bar-item">
              <span class="bar-label">{{ severityLabels[item.severity] || item.severity }}</span>
              <div class="bar-container">
                <div
                  class="bar-fill"
                  :style="{
                    width: (item.count / stats.total * 100) + '%',
                    backgroundColor: severityColors[item.severity] || '#1890ff'
                  }"
                ></div>
              </div>
              <span class="bar-count">{{ item.count }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div style="display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap">
      <a-select
        v-model:value="filterCategory"
        placeholder="选择类别"
        allowClear
        style="width: 150px"
        @change="handleFilterChange"
      >
        <a-select-option value="refund">退款相关</a-select-option>
        <a-select-option value="complaint">投诉相关</a-select-option>
        <a-select-option value="order_cancel">取消订单</a-select-option>
        <a-select-option value="regulatory">监管机构</a-select-option>
        <a-select-option value="fraud">欺诈相关</a-select-option>
      </a-select>
      <a-select
        v-model:value="filterActive"
        placeholder="启用状态"
        allowClear
        style="width: 120px"
        @change="handleFilterChange"
      >
        <a-select-option value="true">已启用</a-select-option>
        <a-select-option value="false">已禁用</a-select-option>
      </a-select>
      <a-select
        v-model:value="filterSeverity"
        placeholder="严重程度"
        allowClear
        style="width: 120px"
        @change="handleFilterChange"
      >
        <a-select-option value="high">高</a-select-option>
        <a-select-option value="medium">中</a-select-option>
        <a-select-option value="low">低</a-select-option>
      </a-select>
    </div>

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
        <template v-if="column.key === 'keyword'">
          <span style="font-weight: 500">{{ record.keyword }}</span>
        </template>
        <template v-if="column.key === 'category'">
          <a-tag :color="categoryColors[record.category] || 'default'">
            {{ categoryLabels[record.category] || record.category }}
          </a-tag>
        </template>
        <template v-if="column.key === 'severity'">
          <a-tag :color="severityColors[record.severity] || 'default'">
            {{ severityLabels[record.severity] || record.severity }}
          </a-tag>
        </template>
        <template v-if="column.key === 'is_active'">
          <a-switch
            :checked="record.is_active"
            size="small"
            @change="(val) => handleToggleActive(record, val)"
          />
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" @click="showEditModal(record)">编辑</a-button>
          <a-popconfirm
            title="确定删除此关键词？"
            @confirm="handleDelete(record.id)"
            ok-text="确定"
            cancel-text="取消"
          >
            <a-button size="small" danger style="margin-left: 8px">删除</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <!-- Create/Edit modal -->
    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑关键词' : '新增关键词'"
      @ok="handleSave"
      :confirmLoading="saving"
      ok-text="确定"
      cancel-text="取消"
    >
      <a-form :model="modalForm" layout="vertical">
        <a-form-item label="关键词" required>
          <a-input v-model:value="modalForm.keyword" placeholder="输入关键词" />
        </a-form-item>
        <a-form-item label="类别" required>
          <a-select v-model:value="modalForm.category" placeholder="选择类别">
            <a-select-option value="refund">退款相关</a-select-option>
            <a-select-option value="complaint">投诉相关</a-select-option>
            <a-select-option value="order_cancel">取消订单</a-select-option>
            <a-select-option value="regulatory">监管机构</a-select-option>
            <a-select-option value="fraud">欺诈相关</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="严重程度">
          <a-select v-model:value="modalForm.severity" placeholder="选择严重程度">
            <a-select-option value="high">高</a-select-option>
            <a-select-option value="medium">中</a-select-option>
            <a-select-option value="low">低</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="是否启用" v-if="isEdit">
          <a-switch v-model:checked="modalForm.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getKeywords, getKeywordStats, createKeyword, updateKeyword, deleteKeyword } from '@/api/keywords'
import { formatTime } from '@/utils/format'
import { message } from 'ant-design-vue'

const data = ref([])
const loading = ref(false)
const saving = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

const stats = ref({
  total: 0,
  active_count: 0,
  inactive_count: 0,
  category_stats: [],
  severity_stats: [],
})

const filterCategory = ref(undefined)
const filterActive = ref(undefined)
const filterSeverity = ref(undefined)

const pagination = reactive({
  current: 1,
  pageSize: 50,
  showSizeChanger: true,
  pageSizeOptions: ['20', '50', '100', '200'],
  showTotal: (total) => `共 ${total} 条`,
  total: 0,
})

const categoryColors = {
  refund: 'red',
  complaint: 'orange',
  order_cancel: 'purple',
  regulatory: 'cyan',
  fraud: 'magenta',
}

const categoryLabels = {
  refund: '退款相关',
  complaint: '投诉相关',
  order_cancel: '取消订单',
  regulatory: '监管机构',
  fraud: '欺诈相关',
}

const severityColors = {
  high: 'red',
  medium: 'orange',
  low: 'green',
}

const severityLabels = {
  high: '高',
  medium: '中',
  low: '低',
}

const modalForm = reactive({
  keyword: '',
  category: 'refund',
  severity: 'medium',
  is_active: true,
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '关键词', dataIndex: 'keyword', key: 'keyword', width: 150 },
  { title: '类别', dataIndex: 'category', key: 'category', width: 120 },
  { title: '严重程度', dataIndex: 'severity', key: 'severity', width: 100 },
  { title: '启用', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { title: '操作', key: 'actions', width: 140, fixed: 'right' },
]

async function loadData() {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filterCategory.value) params.category = filterCategory.value
    if (filterActive.value !== undefined) params.is_active = filterActive.value === 'true'
    if (filterSeverity.value) params.severity = filterSeverity.value

    const res = await getKeywords(params)
    data.value = res.data || []
    pagination.total = res.total || 0
  } catch {
    data.value = []
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const res = await getKeywordStats()
    stats.value = {
      total: res.total || 0,
      active_count: res.active_count || 0,
      inactive_count: res.inactive_count || 0,
      category_stats: res.category_stats || [],
      severity_stats: res.severity_stats || [],
    }
  } catch {
    // 忽略统计加载失败
  }
}

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

function handleFilterChange() {
  pagination.current = 1
  loadData()
}

function showCreateModal() {
  isEdit.value = false
  editId.value = null
  Object.assign(modalForm, {
    keyword: '',
    category: 'refund',
    severity: 'medium',
    is_active: true,
  })
  modalVisible.value = true
}

function showEditModal(record) {
  isEdit.value = true
  editId.value = record.id
  Object.assign(modalForm, {
    keyword: record.keyword,
    category: record.category,
    severity: record.severity,
    is_active: record.is_active,
  })
  modalVisible.value = true
}

async function handleSave() {
  if (!modalForm.keyword.trim()) {
    message.error('请输入关键词')
    return
  }
  if (!modalForm.category) {
    message.error('请选择类别')
    return
  }

  saving.value = true
  try {
    if (isEdit.value) {
      await updateKeyword(editId.value, {
        keyword: modalForm.keyword.trim(),
        category: modalForm.category,
        severity: modalForm.severity,
        is_active: modalForm.is_active,
      })
      message.success('关键词已更新')
    } else {
      await createKeyword({
        keyword: modalForm.keyword.trim(),
        category: modalForm.category,
        severity: modalForm.severity,
      })
      message.success('关键词已创建')
    }
    modalVisible.value = false
    loadData()
    loadStats()
  } catch (err) {
    const detail = err.response?.data?.detail
    if (detail) message.error(detail)
  } finally {
    saving.value = false
  }
}

async function handleToggleActive(record, value) {
  try {
    await updateKeyword(record.id, { is_active: value })
    message.success(value ? '关键词已启用' : '关键词已禁用')
    loadData()
    loadStats()
  } catch (err) {
    const detail = err.response?.data?.detail
    if (detail) message.error(detail)
  }
}

async function handleDelete(id) {
  try {
    await deleteKeyword(id)
    message.success('关键词已删除')
    loadData()
    loadStats()
  } catch (err) {
    const detail = err.response?.data?.detail
    if (detail) message.error(detail)
  }
}

onMounted(() => {
  loadData()
  loadStats()
})
</script>

<style scoped>
.page-card {
  background: #fff;
  padding: 24px;
  border-radius: 8px;
}

.stats-section {
  margin-bottom: 24px;
}

.stats-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  flex: 1;
  padding: 16px 20px;
  border-radius: 8px;
  background: #f5f5f5;
  text-align: center;
}

.stat-card-total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.stat-card-active {
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  color: #fff;
}

.stat-card-inactive {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: #fff;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  opacity: 0.9;
}

.stats-detail {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.stats-group {
  flex: 1;
  min-width: 280px;
}

.stats-group-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid #1890ff;
}

.stats-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stats-bar-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bar-label {
  width: 80px;
  font-size: 13px;
  color: #666;
}

.bar-container {
  flex: 1;
  height: 16px;
  background: #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.bar-count {
  width: 40px;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  text-align: right;
}
</style>