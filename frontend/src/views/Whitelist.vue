<template>
  <div class="page-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">协议话术白名单管理</h3>
      <a-button type="primary" @click="showCreateModal">
        <template #icon><PlusOutlined /></template>
        新增协议话术
      </a-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-section">
      <div class="stats-cards">
        <div class="stat-card stat-card-total">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">话术总数</div>
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
    </div>

    <!-- 筛选区域 -->
    <div style="display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap">
      <a-input
        v-model:value="searchPattern"
        placeholder="搜索话术内容"
        allowClear
        style="width: 200px"
        @change="handleSearch"
      />
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
    </div>

    <a-table
      :columns="columns"
      :data-source="filteredData"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      size="small"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'pattern'">
          <span style="font-weight: 500">{{ record.pattern }}</span>
        </template>
        <template v-if="column.key === 'description'">
          <span style="color: #666">{{ record.description || '-' }}</span>
        </template>
        <template v-if="column.key === 'is_active'">
          <a-switch
            :checked="record.is_active"
            size="small"
            @change="handleToggleActive(record)"
          />
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" @click="showEditModal(record)">编辑</a-button>
          <a-popconfirm
            title="确定删除此协议话术？"
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
      :title="isEdit ? '编辑协议话术' : '新增协议话术'"
      @ok="handleSave"
      :confirmLoading="saving"
      ok-text="确定"
      cancel-text="取消"
    >
      <a-form :model="modalForm" layout="vertical">
        <a-form-item label="话术内容" required>
          <a-input v-model:value="modalForm.pattern" placeholder="输入话术内容" maxlength="100" />
        </a-form-item>
        <a-form-item label="描述说明">
          <a-textarea v-model:value="modalForm.description" placeholder="输入描述说明" :rows="2" maxlength="200" />
        </a-form-item>
        <a-form-item label="是否启用" v-if="isEdit">
          <a-switch v-model:checked="modalForm.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getWhitelistPatterns, createWhitelistPattern, updateWhitelistPattern, deleteWhitelistPattern, toggleWhitelistPattern } from '@/api/whitelist'
import { formatTime } from '@/utils/format'
import { message } from 'ant-design-vue'

const data = ref([])
const loading = ref(false)
const saving = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

const searchPattern = ref('')
const filterActive = ref(undefined)

const stats = computed(() => {
  const total = data.value.length
  const activeCount = data.value.filter(r => r.is_active).length
  return {
    total,
    active_count: activeCount,
    inactive_count: total - activeCount,
  }
})

const filteredData = computed(() => {
  let result = data.value
  if (searchPattern.value) {
    const keyword = searchPattern.value.toLowerCase()
    result = result.filter(r =>
      r.pattern.toLowerCase().includes(keyword) ||
      (r.description && r.description.toLowerCase().includes(keyword))
    )
  }
  if (filterActive.value !== undefined) {
    const isActive = filterActive.value === 'true'
    result = result.filter(r => r.is_active === isActive)
  }
  return result
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100'],
  showTotal: (total) => `共 ${total} 条`,
})

const modalForm = reactive({
  pattern: '',
  description: '',
  is_active: true,
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '话术内容', dataIndex: 'pattern', key: 'pattern', width: 200 },
  { title: '描述说明', dataIndex: 'description', key: 'description' },
  { title: '启用', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { title: '操作', key: 'actions', width: 140, fixed: 'right' },
]

async function loadData() {
  loading.value = true
  try {
    const res = await getWhitelistPatterns()
    data.value = res.data || []
  } catch {
    data.value = []
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
}

function handleSearch() {
  pagination.current = 1
}

function handleFilterChange() {
  pagination.current = 1
}

function showCreateModal() {
  isEdit.value = false
  editId.value = null
  Object.assign(modalForm, {
    pattern: '',
    description: '',
    is_active: true,
  })
  modalVisible.value = true
}

function showEditModal(record) {
  isEdit.value = true
  editId.value = record.id
  Object.assign(modalForm, {
    pattern: record.pattern,
    description: record.description || '',
    is_active: record.is_active,
  })
  modalVisible.value = true
}

async function handleSave() {
  if (!modalForm.pattern.trim()) {
    message.error('请输入话术内容')
    return
  }

  saving.value = true
  try {
    if (isEdit.value) {
      await updateWhitelistPattern(editId.value, {
        pattern: modalForm.pattern.trim(),
        description: modalForm.description.trim(),
        is_active: modalForm.is_active,
      })
      message.success('协议话术已更新')
    } else {
      await createWhitelistPattern({
        pattern: modalForm.pattern.trim(),
        description: modalForm.description.trim(),
      })
      message.success('协议话术已创建')
    }
    modalVisible.value = false
    loadData()
  } catch (err) {
    const detail = err.response?.data?.detail
    if (detail) message.error(detail)
  } finally {
    saving.value = false
  }
}

async function handleToggleActive(record) {
  try {
    await toggleWhitelistPattern(record.id)
    message.success(record.is_active ? '协议话术已禁用' : '协议话术已启用')
    loadData()
  } catch (err) {
    const detail = err.response?.data?.detail
    if (detail) message.error(detail)
  }
}

async function handleDelete(id) {
  try {
    await deleteWhitelistPattern(id)
    message.success('协议话术已删除')
    loadData()
  } catch (err) {
    const detail = err.response?.data?.detail
    if (detail) message.error(detail)
  }
}

onMounted(loadData)
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
}

.stat-card {
  flex: 1;
  padding: 16px 20px;
  border-radius: 8px;
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
</style>