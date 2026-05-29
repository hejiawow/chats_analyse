<template>
  <div>
    <!-- Filter bar -->
    <a-card :bordered="false" style="margin-bottom: 16px">
      <a-form layout="inline" :model="filters">
        <a-form-item label="场景类型">
          <a-select v-model:value="filters.scenario_type" placeholder="全部" style="width: 140px" allow-clear>
            <a-select-option v-for="s in scenarios" :key="s" :value="s">{{ s }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="关键词">
          <a-input v-model:value="filters.keyword" placeholder="搜索关键词" style="width: 180px" allow-clear />
        </a-form-item>
        <a-form-item label="最低分">
          <a-select v-model:value="filters.min_score" placeholder="全部" style="width: 100px" allow-clear>
            <a-select-option :value="0.5">0.5</a-select-option>
            <a-select-option :value="0.6">0.6</a-select-option>
            <a-select-option :value="0.7">0.7</a-select-option>
            <a-select-option :value="0.8">0.8</a-select-option>
            <a-select-option :value="0.9">0.9</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- Card grid -->
    <div v-if="data.length" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; margin-bottom: 16px">
      <a-card
        v-for="r in data" :key="r.id"
        :bordered="false" hoverable class="script-card"
        :style="getCardStyle(r)"
        @click="showDetail(r.id)"
      >
        <template #title>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <div style="display: flex; gap: 6px; flex-wrap: wrap">
              <a-tag :color="r.script_type === '唤醒话术' ? 'warning' : 'success'">{{ r.script_type }}</a-tag>
              <a-tag v-if="r.business_subject" color="blue">{{ r.business_subject }}</a-tag>
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
          <span v-if="r.intent" style="font-size: 12px; color: #94a3b8; margin-left: auto">意图: {{ r.intent }}</span>
        </template>
      </a-card>
    </div>
    <a-empty v-else description="暂无记录" style="margin: 40px 0" />

    <!-- Pagination -->
    <div style="display: flex; justify-content: space-between; align-items: center">
      <span style="font-size: 13px; color: #64748b">共 {{ total }} 条</span>
      <a-pagination v-model:current="currentPage" :total="total" :pageSize="pageSize" size="small" @change="handlePageChange" />
    </div>

    <!-- Detail modal -->
    <a-modal v-model:open="detailVisible" title="话术详情" width="700px" :footer="null">
      <div v-if="detailData">
        <!-- Header info -->
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="话术类型">
            <a-tag :color="detailData.script_type === '唤醒话术' ? 'warning' : 'success'">{{ detailData.script_type }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="好友昵称">{{ detailData.friend_nick || '-' }}</a-descriptions-item>
          <a-descriptions-item label="销售ID">{{ detailData.user_id }}</a-descriptions-item>
          <a-descriptions-item label="好友ID">{{ detailData.friend_id }}</a-descriptions-item>
          <a-descriptions-item label="创建时间" :span="2">{{ formatTime(detailData.created_at) }}</a-descriptions-item>
        </a-descriptions>

        <!-- Wake-up script fields -->
        <template v-if="detailData.script_type === '唤醒话术'">
          <div style="margin-top: 16px">
            <h4 style="margin-bottom: 12px; font-size: 15px">核心内容</h4>
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
            <div v-if="detailData.target_audience" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-top: 8px; font-size: 13px">
              <strong>适用人群：</strong>{{ detailData.target_audience }}
            </div>
          </div>
        </template>

        <!-- Sales script fields -->
        <template v-else>
          <div style="margin-top: 16px">
            <h4 style="margin-bottom: 12px; font-size: 15px">核心内容</h4>
            <div v-if="detailData.customer_question" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-bottom: 8px; font-size: 13px">
              <strong>客户问题：</strong>{{ detailData.customer_question }}
            </div>
            <div v-if="detailData.sales_answer" style="padding: 12px; background: #fef2f2; border-left: 3px solid #ef4444; border-radius: 6px; font-size: 14px; line-height: 1.6">
              <strong>销冠回答：</strong>{{ detailData.sales_answer }}
            </div>
            <div v-if="detailData.applicable_scenario" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-top: 8px; font-size: 13px">
              <strong>适用场景：</strong>{{ detailData.applicable_scenario }}
            </div>
            <div v-if="detailData.customer_intent" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-top: 8px; font-size: 13px">
              <strong>客户意图：</strong>{{ detailData.customer_intent }}
            </div>
          </div>
        </template>

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

        <!-- Meta footer -->
        <div v-if="detailData.tags || detailData.business_subject || (detailData.compliance_risk && detailData.compliance_risk !== '无')" style="margin-top: 20px; padding-top: 12px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #94a3b8; line-height: 1.8">
          <span v-if="detailData.tags">标签：{{ detailData.tags }}</span><br>
          <span v-if="detailData.business_subject">业务科目：{{ detailData.business_subject }}</span><br>
          <span v-if="detailData.compliance_risk && detailData.compliance_risk !== '无'" style="color: #ef4444">合规风险：{{ detailData.compliance_risk }}</span>
        </div>

        <!-- Similar scripts section -->
        <div style="margin-top: 20px; display: flex; justify-content: flex-end">
          <a-button type="primary" :loading="similarLoading" @click="loadSimilarScripts">找相似话术</a-button>
        </div>

        <div v-if="similarScripts.length" style="margin-top: 16px">
          <h4 style="margin-bottom: 12px; font-size: 15px">相似话术 ({{ similarScripts.length }})</h4>
          <a-list :data-source="similarScripts" size="small">
            <template #renderItem="{ item }">
              <a-list-item style="cursor: pointer" @click="showDetail(item.id)">
                <a-list-item-meta>
                  <template #title>
                    <div style="display: flex; align-items: center; gap: 8px">
                      <a-tag :color="item.script_type === '唤醒话术' ? 'warning' : 'success'" size="small">{{ item.script_type }}</a-tag>
                      <span>{{ getSimilarTitle(item) }}</span>
                      <a-tag v-if="item.similarity" color="purple" size="small">{{ (item.similarity * 100).toFixed(0) }}%</a-tag>
                    </div>
                  </template>
                  <template #description>
                    <span style="color: #64748b; font-size: 12px">{{ getSimilarQuote(item) }}</span>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getScriptLibList, getScriptDetail, getScenarios, getSimilarScripts } from '@/api/scriptlib'
import { formatTime } from '@/utils/format'
import { message } from 'ant-design-vue'

const data = ref([])
const scenarios = ref([])
const detailVisible = ref(false)
const detailData = ref(null)
const currentPage = ref(1)
const total = ref(0)
const pageSize = 12
const filters = reactive({ scenario_type: '', keyword: '', min_score: '' })

const similarLoading = ref(false)
const similarScripts = ref([])

function getCardStyle(r) {
  const isWake = r.script_type === '唤醒话术'
  return `border-left: 3px solid ${isWake ? '#f59e0b' : '#10b981'}`
}

function getCardTitle(r) {
  const isWake = r.script_type === '唤醒话术'
  if (isWake) return r.trigger_customer_state || '唤醒话术'
  return r.customer_question || r.scenario_type || '销售话术'
}

function getCardQuote(r) {
  const isWake = r.script_type === '唤醒话术'
  const q = isWake ? (r.wake_script || '') : (r.sales_answer || '')
  return q.length > 100 ? q.substring(0, 100) + '...' : q || '-'
}

async function loadData() {
  try {
    const params = { page: currentPage.value, page_size: pageSize }
    if (filters.scenario_type) params.scenario_type = filters.scenario_type
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.min_score) params.min_score = filters.min_score
    const res = await getScriptLibList(params)
    data.value = res.data || []
    total.value = res.total || 0
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
function handleReset() { filters.scenario_type = ''; filters.keyword = ''; filters.min_score = ''; currentPage.value = 1; loadData() }
function handlePageChange(page) { currentPage.value = page; loadData() }

async function showDetail(id) {
  detailData.value = await getScriptDetail(id)
  similarScripts.value = []
  detailVisible.value = true
}

async function loadSimilarScripts() {
  similarLoading.value = true
  try {
    const res = await getSimilarScripts(detailData.value.id)
    similarScripts.value = res.data || res.results || []
    if (!similarScripts.value.length) {
      message.info('未找到相似话术')
    }
  } catch {
    message.error('获取相似话术失败')
  } finally {
    similarLoading.value = false
  }
}

function getSimilarTitle(item) {
  const isWake = item.script_type === '唤醒话术'
  return isWake ? (item.trigger_customer_state || '唤醒话术') : (item.customer_question || '销售话术')
}

function getSimilarQuote(item) {
  const isWake = item.script_type === '唤醒话术'
  const q = isWake ? (item.wake_script || '') : (item.sales_answer || '')
  return q.length > 80 ? q.substring(0, 80) + '...' : q || '-'
}

onMounted(() => { loadData(); loadScenarios() })
</script>

<style scoped>
.script-card { cursor: pointer; }
.script-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
</style>
