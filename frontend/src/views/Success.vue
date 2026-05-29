<template>
  <div>
    <!-- Filter bar -->
    <a-card :bordered="false" style="margin-bottom: 16px">
      <a-form layout="inline" :model="filters">
        <a-form-item label="销售ID">
          <a-input v-model:value="filters.user_id" placeholder="销售ID" style="width: 180px" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">查询</a-button>
          <a-button style="margin-left: 8px" @click="handleReset">重置</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- Card grid -->
    <div v-if="data.length" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; margin-bottom: 16px">
      <a-card
        v-for="r in data" :key="r.id"
        :bordered="false" hoverable class="case-card"
        :style="r.status === 'no_chat' ? 'border-left: 3px solid #f59e0b' : 'border-left: 3px solid #10b981'"
      >
        <template #title>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <a-tag :color="r.status === 'no_chat' ? 'warning' : 'success'">
              {{ r.status === 'no_chat' ? '无聊天记录' : '已成交' }}
            </a-tag>
            <span style="font-size: 12px; color: #94a3b8">{{ formatTime(r.created_at) }}</span>
          </div>
        </template>
        <div style="font-weight: 600; margin-bottom: 6px; font-size: 14px">
          {{ getBasic(r).sales_style || '销售风格分析' }}
        </div>
        <p style="color: #64748b; font-size: 13px; margin: 0 0 8px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
          {{ getBasic(r).key_sentence || '-' }}
        </p>
        <div style="font-size: 12px; color: #94a3b8; display: flex; gap: 12px; flex-wrap: wrap">
          <span v-if="getBasic(r).deal_time">成交: {{ getBasic(r).deal_time }}</span>
          <span v-if="getBasic(r).chat_duration">时长: {{ getBasic(r).chat_duration }}</span>
          <span v-if="getBasic(r).message_count">消息: {{ getBasic(r).message_count }}条</span>
        </div>
        <template #actions>
          <span style="font-size: 12px; color: #94a3b8">{{ r.user_id }} {{ r.friend_nick || r.friend_id }}</span>
          <a-button size="small" @click.stop="downloadCaseReport(r.id)">下载报告</a-button>
          <a-button type="primary" size="small" @click.stop="showDetail(r)">详情</a-button>
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
    <a-modal v-model:open="detailVisible" title="成交案例详情" width="900px" :footer="null">
      <div v-if="detailData">
        <!-- Basic info -->
        <a-descriptions :column="2" bordered size="small" :title="'基本信息'">
          <a-descriptions-item label="成交时间">{{ getBasic(detailData).deal_time || '-' }}</a-descriptions-item>
          <a-descriptions-item label="聊天时长">{{ getBasic(detailData).chat_duration || '-' }}</a-descriptions-item>
          <a-descriptions-item label="消息数量">{{ getBasic(detailData).message_count || '-' }}</a-descriptions-item>
          <a-descriptions-item label="销售风格">{{ getBasic(detailData).sales_style || '-' }}</a-descriptions-item>
          <a-descriptions-item label="身份定位" :span="2">{{ getUserProfile(detailData).identity || '-' }}</a-descriptions-item>
          <a-descriptions-item label="主要顾虑" :span="2">{{ getUserProfile(detailData).concerns || '-' }}</a-descriptions-item>
          <a-descriptions-item label="核心需求" :span="2">{{ getUserProfile(detailData).needs || '-' }}</a-descriptions-item>
          <a-descriptions-item label="痛点" :span="2">{{ getUserProfile(detailData).pain_points || '-' }}</a-descriptions-item>
        </a-descriptions>

        <!-- Journey timeline -->
        <div v-if="getJourney(detailData).length" style="margin-top: 20px">
          <h4 style="margin-bottom: 12px; font-size: 15px; color: #10b981">沟通历程</h4>
          <a-timeline>
            <a-timeline-item v-for="(stage, idx) in getJourney(detailData)" :key="idx" :color="getStageColor(idx)">
              <template #dot>
                <span style="font-weight: 700; color: #10b981; font-size: 13px">P{{ idx + 1 }}</span>
              </template>
              <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px">
                {{ stage.stage_name || '阶段' + (idx + 1) }}
                <span v-if="stage.time_range" style="font-weight: 400; font-size: 12px; color: #94a3b8; margin-left: 8px">
                  {{ stage.time_range }}
                </span>
              </div>
              <div style="font-size: 13px; line-height: 1.6">
                <div v-if="stage.sales_action"><strong>销售动作：</strong>{{ stage.sales_action }}</div>
                <div v-if="stage.user_reaction"><strong>用户反应：</strong>{{ stage.user_reaction }}</div>
                <div v-if="stage.effectiveness" style="margin-top: 4px">
                  <strong>效果评分：</strong>
                  <span v-for="d in 5" :key="d" style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 3px; background: d <= getEffectivenessScore(stage) ? '#10b981' : '#e2e8f0'"></span>
                </div>
              </div>
            </a-timeline-item>
          </a-timeline>
        </div>

        <!-- Scripts -->
        <div v-if="getScripts(detailData).length" style="margin-top: 20px">
          <h4 style="margin-bottom: 12px; font-size: 15px; color: #6366f1">关键话术</h4>
          <a-card v-for="(s, idx) in getScripts(detailData)" :key="idx" size="small" style="margin-bottom: 12px" :bordered="false">
            <div style="margin-bottom: 6px">
              <a-tag v-if="s.scene_tag" color="blue">{{ s.scene_tag }}</a-tag>
              <a-tag v-if="s.customer_intent" color="orange">{{ s.customer_intent }}</a-tag>
              <!-- <a-tag v-for="t in (s.tags || [])" :key="t" color="purple">{{ t }}</a-tag> -->
            </div>
            <div v-if="s.customer_question" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-bottom: 8px; font-size: 13px">
              <strong>客户提问：</strong>{{ s.customer_question }}
            </div>
            <div v-if="s.sales_answer" style="padding: 10px 12px; background: #f0fdf4; border-left: 3px solid #10b981; border-radius: 6px; font-size: 14px; line-height: 1.6">
              <strong>销冠回答：</strong>{{ s.sales_answer }}
            </div>
            <div v-if="s.why_good" style="margin-top: 8px; padding: 8px 12px; background: #fffbeb; border-radius: 6px; font-size: 13px">
              <strong>好在哪儿：</strong>{{ s.why_good }}
            </div>
          </a-card>
        </div>

        <!-- Psychology -->
        <div v-if="getPsychology(detailData).length" style="margin-top: 20px">
          <h4 style="margin-bottom: 12px; font-size: 15px; color: #f59e0b">客户心理变化</h4>
          <a-card size="small" :bordered="false">
            <div v-for="(p, idx) in getPsychology(detailData)" :key="idx" style="margin-bottom: 8px; padding: 8px 0; border-bottom: 1px solid #f1f5f9">
              <strong style="font-size: 13px">{{ p.mental_state || '心理状态' }}</strong>
              <a-arrow-right-outlined style="margin: 0 6px; font-size: 12px; color: #94a3b8" />
              <a-tag color="green">{{ p.trigger || '触发点' }}</a-tag>
            </div>
          </a-card>
        </div>

        <!-- Key factors -->
        <div style="margin-top: 20px">
          <h4 style="margin-bottom: 12px; font-size: 15px; color: #ef4444">成交关键因素</h4>
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="关键话术">{{ getFactors(detailData).key_sentence || '-' }}</a-descriptions-item>
            <a-descriptions-item label="成交节点">{{ getFactors(detailData).deal_node || '-' }}</a-descriptions-item>
            <a-descriptions-item label="三大优势">{{ getFactors(detailData).top3_strengths || '-' }}</a-descriptions-item>
          </a-descriptions>
        </div>

        <!-- Improvements -->
        <div v-if="getImprovements(detailData).flaws || getImprovements(detailData).optimization_suggestions?.length" style="margin-top: 20px">
          <h4 style="margin-bottom: 12px; font-size: 15px; color: #8b5cf6">优化建议</h4>
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item v-if="getImprovements(detailData).flaws" label="不足之处">{{ getImprovements(detailData).flaws }}</a-descriptions-item>
          </a-descriptions>
          <div v-for="(opt, idx) in (getImprovements(detailData).optimization_suggestions || [])" :key="idx" style="margin-top: 8px; padding: 12px; background: #faf5ff; border-radius: 6px; border: 1px solid #e9d5ff">
            <div style="font-size: 13px; margin-bottom: 4px">
              <span style="color: #94a3b8">原话：</span>{{ opt.original || '-' }}
            </div>
            <div style="font-size: 13px">
              <span style="color: #10b981; font-weight: 600">优化：</span>{{ opt.better || '-' }}
            </div>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getSalesJourneys, getSalesJourneyDetail } from '@/api/journey'
import { formatTime } from '@/utils/format'
import { message } from 'ant-design-vue'
import { ArrowRightOutlined } from '@ant-design/icons-vue'

const data = ref([])
const detailVisible = ref(false)
const detailData = ref(null)
const currentPage = ref(1)
const total = ref(0)
const pageSize = 12
const filters = reactive({ user_id: '' })

function getBasic(item) {
  return item?.analysis_result?.module1_basic || {}
}

function getUserProfile(item) {
  return item?.analysis_result?.module1_basic?.user_profile || {}
}

function getJourney(item) {
  return item?.analysis_result?.module2_journey || []
}

function getScripts(item) {
  return item?.analysis_result?.module3_scripts || []
}

function getPsychology(item) {
  return item?.analysis_result?.module4_psychology || []
}

function getFactors(item) {
  return item?.analysis_result?.module5_key_factors || {}
}

function getImprovements(item) {
  return item?.analysis_result?.module6_improvements || {}
}

function getStageColor(idx) {
  const colors = ['blue', 'green', 'orange', 'purple', 'cyan', 'red']
  return colors[idx % colors.length]
}

function getEffectivenessScore(stage) {
  const score = stage.effectiveness
  if (typeof score === 'number') return Math.min(Math.max(score, 0), 5)
  if (typeof score === 'string') {
    const n = parseInt(score, 10)
    if (!isNaN(n)) return Math.min(Math.max(n, 0), 5)
  }
  return 0
}

async function loadData() {
  try {
    const params = { page: currentPage.value, page_size: pageSize }
    if (filters.user_id) params.user_id = filters.user_id
    const res = await getSalesJourneys(params)
    data.value = res.data || []
    total.value = res.total || 0
  } catch {
    data.value = []
  }
}

function handleSearch() { currentPage.value = 1; loadData() }
function handleReset() { filters.user_id = ''; currentPage.value = 1; loadData() }
function handlePageChange(page) { currentPage.value = page; loadData() }

async function showDetail(item) {
  try {
    detailData.value = await getSalesJourneyDetail(item.id)
    detailVisible.value = true
  } catch {
    message.error('获取详情失败')
  }
}

function downloadCaseReport(id) {
  const token = localStorage.getItem('token')
  const url = `/api/sales-journeys/${id}/download`
  fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
    .then(r => r.blob())
    .then(blob => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `成交案例_${id}.html`
      a.click()
    })
  message.success('正在下载报告...')
}

onMounted(() => { loadData() })
</script>

<style scoped>
.case-card { cursor: pointer; }
.case-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
</style>
