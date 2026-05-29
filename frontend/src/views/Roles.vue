<template>
  <div class="page-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">角色管理</h3>
      <a-button type="primary" @click="showCreateModal">
        <template #icon><PlusOutlined /></template>
        新增角色
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
        <template v-if="column.key === 'permissions'">
          <a-tag v-for="p in record.permissions" :key="p" color="blue" style="margin: 2px">{{ p }}</a-tag>
          <span v-if="!record.permissions?.length" style="color: #94a3b8">-</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" @click="showEditModal(record)">编辑</a-button>
          <a-popconfirm title="确定删除此角色？" @confirm="handleDelete(record.id)" ok-text="确定" cancel-text="取消">
            <a-button size="small" danger style="margin-left: 8px">删除</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <!-- Create/Edit modal -->
    <a-modal v-model:open="modalVisible" :title="isEdit ? '编辑角色' : '新增角色'" @ok="handleSave" :confirmLoading="saving">
      <a-form :model="modalForm" layout="vertical">
        <a-form-item label="角色名称">
          <a-input v-model:value="modalForm.name" :disabled="isEdit" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="modalForm.description" :rows="2" />
        </a-form-item>
        <a-form-item label="权限">
          <a-checkbox-group v-model:value="modalForm.permissions" style="display: flex; flex-direction: column; gap: 8px">
            <a-checkbox v-for="p in allPermissions" :key="p.value" :value="p.value">
              {{ p.label }}
            </a-checkbox>
          </a-checkbox-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getRoles, createRole, updateRole, deleteRole } from '@/api/roles'
import { formatTime } from '@/utils/format'
import { message } from 'ant-design-vue'

const data = ref([])
const loading = ref(false)
const saving = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const pagination = reactive({ current: 1, pageSize: 20, showSizeChanger: false, showTotal: (total) => `共 ${total} 条` })

const allPermissions = [
  { value: 'read:dashboard', label: '查看工作台' },
  { value: 'write:trigger', label: '触发分析' },
  { value: 'read:referral', label: '查看转介绍' },
  { value: 'read:cases', label: '查看优秀案例' },
  { value: 'read:journey', label: '查看成交案例' },
  { value: 'read:followup', label: '查看督学合规' },
  { value: 'read:scriptlib', label: '查看话术库' },
  { value: 'write:scriptlib', label: '存入话术库' },
  { value: 'read:rag', label: '使用RAG问答' },
  { value: 'read:agents', label: '查看智能体' },
  { value: 'admin:user', label: '用户管理' },
  { value: 'admin:role', label: '角色管理' },
  { value: 'admin:all', label: '所有权限（超级管理员）' },
]

const modalForm = reactive({ name: '', description: '', permissions: [] })

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '角色名称', dataIndex: 'name', key: 'name', width: 140 },
  { title: '描述', dataIndex: 'description', key: 'description' },
  { title: '权限', key: 'permissions' },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }) => formatTime(text) },
  { title: '操作', key: 'actions', width: 140, fixed: 'right' },
]

async function loadData() {
  loading.value = true
  try {
    const res = await getRoles({ page: pagination.current, page_size: pagination.pageSize })
    data.value = res.data || []
    pagination.total = res.total || 0
  } catch {
    data.value = []
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag) { pagination.current = pag.current; pagination.pageSize = pag.pageSize; loadData() }

function showCreateModal() {
  isEdit.value = false
  editId.value = null
  Object.assign(modalForm, { name: '', description: '', permissions: [] })
  modalVisible.value = true
}

function showEditModal(record) {
  isEdit.value = true
  editId.value = record.id
  Object.assign(modalForm, {
    name: record.name,
    description: record.description || '',
    permissions: [...(record.permissions || [])],
  })
  modalVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (isEdit.value) {
      await updateRole(editId.value, {
        description: modalForm.description,
        permissions: modalForm.permissions,
      })
      message.success('角色已更新')
    } else {
      await createRole({
        name: modalForm.name,
        description: modalForm.description,
        permissions: modalForm.permissions,
      })
      message.success('角色已创建')
    }
    modalVisible.value = false
    loadData()
  } catch {}
  finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  try {
    await deleteRole(id)
    message.success('角色已删除')
    loadData()
  } catch {}
}

onMounted(loadData)
</script>
