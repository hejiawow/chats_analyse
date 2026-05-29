<template>
  <div class="page-card">
    <a-empty description="智能体管理页面 - 待开发" />
    <a-row :gutter="[16, 16]" style="margin-top: 24px">
      <a-col :span="6" v-for="agent in agents" :key="agent.name">
        <a-card :bordered="false" hoverable>
          <template #title>
            <div style="display: flex; align-items: center; gap: 8px">
              <component :is="agent.icon" />
              <span>{{ agent.label }}</span>
            </div>
          </template>
          <a-tag :color="agent.status === 'active' ? 'success' : 'warning'">
            {{ agent.status === 'active' ? '运行中' : '开发中' }}
          </a-tag>
          <p style="color: #94a3b8; font-size: 13px; margin: 8px 0 0">{{ agent.desc }}</p>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  ShareAltOutlined,
  FileTextOutlined,
  TrophyOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'

const agents = ref([
  { name: 'referral', label: '转介绍检测', icon: ShareAltOutlined, status: 'active', desc: '检测销售是否主动向客户推荐其他产品或服务' },
  { name: 'case', label: '优秀话术提取', icon: FileTextOutlined, status: 'active', desc: '从聊天记录中提取优秀的销售话术和唤醒话术' },
  { name: 'journey', label: '优秀成交案例提取', icon: TrophyOutlined, status: 'active', desc: '分析成交案例，总结销售方法和策略' },
  { name: 'follow_up', label: '督学跟进合规检测', icon: CheckCircleOutlined, status: 'active', desc: '检测跟进频率和合规性，生成合规报告' },
])
</script>
