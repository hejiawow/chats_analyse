<template>
  <div class="page-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <a-form layout="inline" :model="filters">
        <a-form-item label="用户名">
          <a-input v-model:value="filters.username" placeholder="用户名" style="width: 140px" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="filters.status" placeholder="全部" style="width: 120px" allow-clear>
            <a-select-option value="active">正常</a-select-option>
            <a-select-option value="disabled">禁用</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
        </a-form-item>
      </a-form>
      <a-button type="primary" @click="showCreateModal">
        <template #icon><PlusOutlined /></template>
        新增用户
      </a-button>
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
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'success' : 'default'">
            {{ record.status === 'active' ? '正常' : '禁用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'roles'">
          <a-tag v-for="r in record.roles" :key="r" color="blue" style="margin-right: 4px">{{ r }}</a-tag>
          <span v-if="!record.roles?.length" style="color: #94a3b8">-</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" @click="showEditModal(record)">编辑</a-button>
          <a-popconfirm title="确定删除此用户？" @confirm="handleDelete(record.id)" ok-text="确定" cancel-text="取消">
            <a-button size="small" danger style="margin-left: 8px">删除</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <!-- Create/Edit modal -->
    <a-modal v-model:open="modalVisible" :title="isEdit ? '编辑用户' : '新增用户'" @ok="handleSave" :confirmLoading="saving">
      <a-form :model="modalForm" layout="vertical">
        <a-form-item label="用户名">
          <a-input v-model:value="modalForm.username" :disabled="isEdit" />
        </a-form-item>
        <a-form-item v-if="!isEdit" label="密码">
          <a-input-password v-model:value="modalForm.password" />
        </a-form-item>
        <a-form-item label="邮箱">
          <a-input v-model:value="modalForm.email" />
        </a-form-item>
        <a-form-item label="手机号">
          <a-input v-model:value="modalForm.phone" />
        </a-form-item>
        <a-form-item label="状态">
          <a-radio-group v-model:value="modalForm.status">
            <a-radio value="active">正常</a-radio>
            <a-radio value="disabled">禁用</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="角色">
          <a-select v-model:value="modalForm.role_ids" mode="multiple" placeholder="选择角色">
            <a-select-option v-for="r in allRoles" :key="r.id" :value="r.id">{{ r.name }}（{{ r.description }}）</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getUsers, createUser, updateUser, deleteUser, assignRoles } from '@/api/users'
import { getRoles } from '@/api/roles'
import { formatTime } from '@/utils/format'
import { message } from 'ant-design-vue'

const data = ref([])
const allRoles = ref([])
const loading = ref(false)
const saving = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const pagination = reactive({ current: 1, pageSize: 20, showSizeChanger: false, showTotal: (total) => `共 ${total} 条` })
const filters = reactive({ username: '', status: '' })
const modalForm = reactive({ username: '', password: '', email: '', phone: '', status: 'active', role_ids: [] })

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '用户名', dataIndex: 'username', key: 'username', width: 120 },
  { title: '邮箱', dataIndex: 'email', key: 'email', width: 180 },
  { title: '手机号', dataIndex: 'phone', key: 'phone', width: 130 },
  { title: '状态', key: 'status', width: 80 },
  { title: '角色', key: 'roles' },
  { title: '最后登录', dataIndex: 'last_login', key: 'last_login', width: 170, customRender: ({ text }) => formatTime(text) },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }) => formatTime(text) },
  { title: '操作', key: 'actions', width: 160, fixed: 'right' },
]

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (filters.username) params.username = filters.username
    if (filters.status) params.status = filters.status
    const res = await getUsers(params)
    data.value = res.data || []
    pagination.total = res.total || 0
  } catch {
    data.value = []
  } finally {
    loading.value = false
  }
}

async function loadRoles() {
  try {
    const res = await getRoles({ page: 1, page_size: 100 })
    allRoles.value = res.data || []
  } catch {}
}

function handleSearch() { pagination.current = 1; loadData() }
function handleReset() { filters.username = ''; filters.status = ''; pagination.current = 1; loadData() }
function handleTableChange(pag) { pagination.current = pag.current; pagination.pageSize = pag.pageSize; loadData() }

function showCreateModal() {
  isEdit.value = false
  editId.value = null
  Object.assign(modalForm, { username: '', password: '', email: '', phone: '', status: 'active', role_ids: [] })
  modalVisible.value = true
}

function showEditModal(record) {
  isEdit.value = true
  editId.value = record.id
  Object.assign(modalForm, {
    username: record.username,
    password: '',
    email: record.email || '',
    phone: record.phone || '',
    status: record.status || 'active',
    role_ids: (record.roles || []).map((r, i) => i), // simplified, use actual role ids from API
  })
  // Map role names to ids
  modalForm.role_ids = allRoles.value.filter(r => (record.role_names || []).includes(r.name)).map(r => r.id)
  modalVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (isEdit.value) {
      await updateUser(editId.value, {
        email: modalForm.email,
        phone: modalForm.phone,
        status: modalForm.status,
      })
      if (modalForm.role_ids.length) {
        await assignRoles(editId.value, modalForm.role_ids)
      }
      message.success('用户已更新')
    } else {
      await createUser({
        username: modalForm.username,
        password: modalForm.password,
        email: modalForm.email,
        phone: modalForm.phone,
        status: modalForm.status,
      })
      message.success('用户已创建')
    }
    modalVisible.value = false
    loadData()
  } catch {
    // error already shown by interceptor
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  try {
    await deleteUser(id)
    message.success('用户已删除')
    loadData()
  } catch {}
}

onMounted(() => { loadData(); loadRoles() })
</script>
