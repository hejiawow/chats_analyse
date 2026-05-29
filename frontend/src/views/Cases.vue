<template>
  <div>
    <!-- Filter bar -->
    <a-card :bordered="false" style="margin-bottom: 16px">
      <a-form layout="inline" :model="filters">
        <a-form-item label="销售ID">
          <a-input v-model:value="filters.user_id" placeholder="销售ID" style="width: 140px" />
        </a-form-item>
        <a-form-item label="话术类型">
          <a-select v-model:value="filters.script_type" placeholder="全部" style="width: 130px" allow-clear>
            <a-select-option value="销售话术">销售话术</a-select-option>
            <a-select-option value="唤醒话术">唤醒话术</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="场景类型">
          <a-select v-model:value="filters.scenario_type" placeholder="全部" style="width: 140px" allow-clear>
            <a-select-option v-for="s in scenarios" :key="s" :value="s">{{ s }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- Selection toolbar -->
    <div v-if="data.length" class="selection-toolbar">
      <div class="toolbar-left">
        <a-checkbox v-model:checked="allSelected" @change="handleSelectAll">
          已选 {{ selectedIds.size }} 条
        </a-checkbox>
      </div>
      <div class="toolbar-right">
        <a-button size="small" @click="handleSelectAll" :disabled="allSelected">全选</a-button>
        <a-button size="small" @click="handleClearSelection" :disabled="!selectedIds.size">清空</a-button>
        <a-button type="primary" size="small" @click="handleExport" :disabled="!selectedIds.size" style="margin-left: 8px">
          <template #icon><DownloadOutlined /></template>
          导出话术 ({{ selectedIds.size }})
        </a-button>
      </div>
    </div>

    <!-- Card grid -->
    <div v-if="data.length" class="card-grid">
      <a-card
        v-for="r in data" :key="r.id"
        :bordered="false" hoverable class="case-card"
        :class="{ 'case-card-selected': selectedIds.has(r.id) }"
        :style="r.status === 'failed' ? 'border-left: 3px solid #ef4444' : r.status === 'no_cases' ? 'border-left: 3px solid #f59e0b' : getRiskCardStyle(r)"
        @click="toggleSelect(r.id)"
      >
        <template #title>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-direction: column; gap: 4px">
            <div style="display: flex; gap: 6px; align-items: center; flex-wrap: nowrap">
              <a-tag v-if="r.applicable_scenario" color="cyan">{{ r.applicable_scenario }}</a-tag>
              <a-tag v-else color="blue">{{ getScriptType(r).label }}</a-tag>
              <a-tag v-if="r.business_subject" color="blue">{{ r.business_subject }}</a-tag>
              <a-tag v-if="r.compliance_risk && r.compliance_risk !== '无'" class="risk-tag" style="font-weight: 600">有风险</a-tag>
            </div>
            <span style="font-size: 12px; color: #94a3b8">{{ formatTime(r.created_at) }}</span>
          </div>
        </template>
        <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px">
          {{ getCardTitle(r) }}
        </div>
        <p style="color: #64748b; font-size: 13px; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
          {{ getCardQuote(r) }}
        </p>
        <template #actions>
          <span style="font-size: 12px; color: #94a3b8">{{ r.user_id }} · {{ r.friend_nick || r.friend_id }}</span>
          <a-button size="small" @click.stop="addToRag(r.id)" class="rag-btn" style="margin-left: auto">存入话术库</a-button>
          <a-button size="small" @click.stop="showDetail(r.id)" class="detail-btn" style="margin-left: 4px">详情</a-button>
        </template>
      </a-card>
    </div>
    <a-empty v-else description="暂无记录" style="margin: 40px 0" />

    <!-- Pagination -->
    <div v-if="data.length" style="display: flex; justify-content: space-between; align-items: center">
      <span style="font-size: 13px; color: #64748b">共 {{ total }} 条</span>
      <a-pagination v-model:current="currentPage" :total="total" :pageSize="pageSize" size="small" @change="handlePageChange" />
    </div>

    <!-- Detail modal -->
    <a-modal v-model:open="detailVisible" title="话术详情" width="700px" :footer="null">
      <div v-if="detailData">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="销售ID">{{ detailData.user_id }}</a-descriptions-item>
          <a-descriptions-item label="好友ID">{{ detailData.friend_id }}</a-descriptions-item>
          <a-descriptions-item label="好友昵称">{{ detailData.friend_nick || '-' }}</a-descriptions-item>
          <a-descriptions-item label="话术类型">
            <a-tag v-if="detailData.applicable_scenario" color="cyan">{{ detailData.applicable_scenario }}</a-tag>
            <a-tag v-else :color="getScriptType(detailData).isWake ? 'warning' : 'success'">{{ getScriptType(detailData).label }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ formatTime(detailData.created_at) }}</a-descriptions-item>
        </a-descriptions>

        <div style="margin-top: 16px; display: flex; justify-content: flex-end">
          <a-button class="rag-btn" @click="addToRag(detailData.id)">存入话术库</a-button>
        </div>

        <!-- Core content -->
        <div style="margin-top: 20px">
          <h4 style="margin-bottom: 12px; font-size: 15px">核心内容</h4>
          <template v-if="!getScriptType(detailData).isWake">
            <div v-if="detailData.customer_question" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-bottom: 8px; font-size: 13px">
              <strong>客户问题：</strong>{{ detailData.customer_question }}
            </div>
            <div v-if="detailData.sales_answer" style="padding: 12px; background: #fef2f2; border-left: 3px solid #ef4444; border-radius: 6px; font-size: 14px; line-height: 1.6">
              <strong>销冠回答：</strong>{{ detailData.sales_answer }}
            </div>
          </template>
          <template v-else>
            <div v-if="detailData.trigger_customer_state" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-bottom: 8px; font-size: 13px">
              <strong>触发客户状态：</strong>{{ detailData.trigger_customer_state }}
            </div>
            <div v-if="detailData.wake_script" style="padding: 12px; background: #fffbeb; border-left: 3px solid #f59e0b; border-radius: 6px; font-size: 14px; line-height: 1.6">
              <strong>销冠唤醒话术：</strong>{{ detailData.wake_script }}
            </div>
            <div v-if="detailData.applicable_scenario" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-top: 8px; font-size: 13px">
              <strong>适用场景：</strong>{{ detailData.applicable_scenario }}
            </div>
            <div v-if="detailData.script_objective" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-top: 8px; font-size: 13px">
              <strong>话术核心目标：</strong>{{ detailData.script_objective }}
            </div>
          </template>
        </div>

        <!-- Design analysis -->
        <div v-if="detailData.core_design_logic" style="margin-top: 20px">
          <h4 style="margin-bottom: 12px; font-size: 15px; color: #10b981">话术拆解</h4>
          <div style="padding: 12px; background: #f0fdf4; border-radius: 6px; font-size: 14px; line-height: 1.6">
            <strong>核心设计逻辑：</strong>{{ detailData.core_design_logic }}
          </div>
          <div v-if="detailData.key_techniques" style="padding: 8px 12px; background: #f0fdf4; border-radius: 6px; margin-top: 8px; font-size: 13px">
            <strong>话术关键技巧：</strong>{{ detailData.key_techniques }}
          </div>
        </div>

        <!-- Pitfall -->
        <div v-if="detailData.pitfall_avoid" style="margin-top: 20px">
          <h4 style="margin-bottom: 12px; font-size: 15px; color: #f59e0b">反例避坑</h4>
          <div style="padding: 12px; background: #fffbeb; border-radius: 6px; border: 1px solid #fef3c7; font-size: 14px; line-height: 1.6">
            {{ detailData.pitfall_avoid }}
          </div>
        </div>

        <!-- Bottom meta -->
        <div v-if="detailData.tags || detailData.business_subject || (detailData.compliance_risk && detailData.compliance_risk !== '无')" style="margin-top: 20px; padding-top: 12px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #94a3b8; line-height: 1.8">
          <span v-if="detailData.tags">标签：{{ detailData.tags }}</span><br>
          <span v-if="detailData.business_subject">业务科目：{{ detailData.business_subject }}</span><br>
          <span v-if="detailData.compliance_risk && detailData.compliance_risk !== '无'" style="color: #ef4444">合规风险：{{ detailData.compliance_risk }}</span>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { DownloadOutlined } from '@ant-design/icons-vue'
import { getCasesList, getCaseDetail, addToRag as addToRagApi } from '@/api/cases'
import { getScenarios } from '@/api/scriptlib'
import { formatTime } from '@/utils/format'
import { message } from 'ant-design-vue'

const data = ref([])
const scenarios = ref([])
const detailVisible = ref(false)
const detailData = ref(null)
const currentPage = ref(1)
const total = ref(0)
const pageSize = 12
const filters = reactive({ user_id: '', script_type: '', scenario_type: '' })

// Selection state
const selectedIds = ref(new Set())
const allSelected = ref(false)

function getScriptType(r) {
  const t = r.script_type || '销售话术'
  return { label: t, isWake: t === '唤醒话术' }
}

function getCardStyle(r) {
  const isWake = r.script_type === '唤醒话术'
  return `border-left: 3px solid ${isWake ? '#f59e0b' : '#10b981'}`
}

function getRiskCardStyle(r) {
  if (r.compliance_risk && r.compliance_risk !== '无') return 'border-left: 3px solid #dc2626'
  return getCardStyle(r)
}

function getCardTitle(r) {
  if (r.status === 'failed') return '提取失败'
  if (r.status === 'no_cases') return '未检测到话术'
  const isWake = r.script_type === '唤醒话术'
  return isWake ? (r.trigger_customer_state || '唤醒话术') : (r.customer_question || '销售话术')
}

function getCardQuote(r) {
  if (r.status !== 'success') return r.error_msg || '该聊天记录中未发现符合要求的优秀话术'
  const isWake = r.script_type === '唤醒话术'
  const q = isWake ? (r.wake_script || '') : (r.sales_answer || '')
  return q.length > 100 ? q.substring(0, 100) + '...' : q || '-'
}

async function loadData() {
  try {
    const params = { page: currentPage.value, page_size: pageSize }
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.script_type) params.script_type = filters.script_type
    if (filters.scenario_type) params.scenario_type = filters.scenario_type
    const res = await getCasesList(params)
    data.value = res.data || []
    total.value = res.total || 0
    // Keep selection across pages, just update allSelected state
    allSelected.value = data.value.length > 0 && data.value.every(r => selectedIds.value.has(r.id))
  } catch {
    data.value = []
  }
}

async function loadScenarios() {
  try {
    const res = await getScenarios()
    scenarios.value = res.scenarios || []
  } catch {}
}

function handleSearch() { currentPage.value = 1; loadData() }
function handleReset() { filters.user_id = ''; filters.script_type = ''; filters.scenario_type = ''; currentPage.value = 1; loadData() }
function handlePageChange(page) { currentPage.value = page; loadData() }

// Selection
function handleSelectAll() {
  if (allSelected.value) {
    // Unselect current page only
    data.value.forEach(r => selectedIds.value.delete(r.id))
    allSelected.value = false
  } else {
    // Select all on current page only
    data.value.forEach(r => selectedIds.value.add(r.id))
    allSelected.value = true
  }
}

function toggleSelect(id) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  allSelected.value = data.value.length > 0 && data.value.every(r => selectedIds.value.has(r.id))
}

function handleClearSelection() {
  selectedIds.value = new Set()
  allSelected.value = false
}

// Export to Markdown
async function handleExport() {
  if (!selectedIds.value.size) {
    message.warning('请先选择要导出的话术')
    return
  }

  message.loading({ content: '正在获取话术详情...', key: 'export', duration: 0 })

  try {
    const details = []
    const selectedArray = Array.from(selectedIds.value)

    for (const id of selectedArray) {
      try {
        // Check if we already have full detail in current page data
        const cached = data.value.find(r => r.id === id)
        if (cached && cached.core_design_logic !== undefined) {
          details.push(cached)
        } else {
          const detail = await getCaseDetail(id)
          details.push(detail)
        }
      } catch (err) {
        console.warn(`Failed to fetch detail for id ${id}:`, err)
        // Fallback to list item
        const item = data.value.find(r => r.id === id)
        if (item) details.push(item)
      }
    }

    const markdown = generateMarkdown(details)
    downloadFile(markdown, `话术导出_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}.md`)
    message.success({ content: `已导出 ${details.length} 条话术`, key: 'export' })
  } catch (err) {
    message.error({ content: '导出失败: ' + (err.message || '未知错误'), key: 'export' })
  }
}

function generateMarkdown(items) {
  let md = '# 优秀话术导出文档\n\n'
  md += `> 导出时间：${new Date().toLocaleString('zh-CN')}\n`
  md += `> 话术总数：${items.length} 条\n`
  md += `> 数据来源：AI会话分析平台\n\n`
  md += `---\n\n`

  items.forEach((item, index) => {
    const isWake = getScriptType(item).isWake
    const scriptContent = isWake ? (item.wake_script || '') : (item.sales_answer || '')

    // Separator
    md += `---\n\n`

    // Header with index
    md += `## 话术 #${index + 1}\n\n`

    // Metadata block
    md += `### 元数据\n\n`
    md += `| 字段 | 值 |\n`
    md += `|------|------|\n`
    md += `| 业务科目 | ${item.business_subject || '-'} |\n`
    if (item.tags) md += `| 标签 | ${item.tags} |\n`
    if (item.compliance_risk && item.compliance_risk !== '无') {
      md += `| 合规风险 | ⚠️ ${item.compliance_risk} |\n`
    }
    md += `\n`

    // Core content
    if (isWake) {
      md += `### 唤醒话术\n\n`
      md += `**触发客户状态：** ${item.trigger_customer_state || '-'}\n\n`
      md += `**销冠唤醒话术：**\n\n`
      md += `> ${scriptContent}\n\n`
      if (item.script_objective) {
        md += `**话术核心目标：** ${item.script_objective}\n\n`
      }
      if (item.applicable_scenario) {
        md += `**适用场景：** ${item.applicable_scenario}\n\n`
      }
    } else {
      md += `### 销售话术\n\n`
      md += `**客户问题：** ${item.customer_question || '-'}\n\n`
      md += `**销冠回答：**\n\n`
      md += `> ${scriptContent}\n\n`
    }

    // Design analysis
    if (item.core_design_logic) {
      md += `### 话术拆解\n\n`
      md += `**核心设计逻辑：** ${item.core_design_logic}\n\n`
      if (item.key_techniques) {
        md += `**话术关键技巧：** ${item.key_techniques}\n\n`
      }
    }

    // Pitfall / anti-example
    if (item.pitfall_avoid) {
      md += `### 反例避坑\n\n`
      md += `> ⚠️ 以下为错误示范，请避免：\n\n`
      md += `${item.pitfall_avoid}\n\n`
    }
  })

  return md
}

function downloadFile(content, filename) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

async function showDetail(id) {
  detailData.value = await getCaseDetail(id)
  detailVisible.value = true
}

async function addToRag(id) {
  try {
    const res = await addToRagApi(id)
    message.success(`已存入话术库 (ID: ${res.rag_id})`)
  } catch (err) {
    if (err.message?.includes('409')) {
      message.warning('该话术已在库中')
    }
  }
}

onMounted(() => { loadData(); loadScenarios() })
</script>

<style scoped>
/* Selection toolbar */
.selection-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  margin-bottom: 16px;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 8px;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Card grid */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.case-card { cursor: pointer; }
.case-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }

.case-card-selected {
  border: 1.5px solid #4f46e5 !important;
  background: #f5f3ff;
}

.rag-btn {
  background: #eef2ff;
  color: #4f46e5;
  border: 1px solid #c7d2fe;
}
.rag-btn:hover {
  background: #e0e7ff;
  border-color: #a5b4fc;
}

.detail-btn {
  background: #f1f5f9;
  color: #64748b;
  border: 1px solid #e2e8f0;
}
.detail-btn:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.risk-tag {
  background: transparent;
  color: #dc2626;
  border: 1px solid #dc2626;
}
</style>
