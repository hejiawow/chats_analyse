<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider v-model:collapsed="collapsed" collapsible theme="dark" width="220">
      <div class="logo">
        <img src="/assets/favicon.svg" alt="logo" class="logo-icon" />
        <h1>AI会话分析平台</h1>
        <!-- <p>销售合规分析平台</p> -->
      </div>
      <a-menu
        v-model:selectedKeys="selectedKeys"
        theme="dark"
        mode="inline"
        @click="handleMenuClick"
      >
        <template v-for="item in visibleMenuItems" :key="item.key">
          <a-menu-divider v-if="item.isDivider" />
          <a-menu-item v-else :key="item.key">
            <component :is="item.icon" />
            <span>{{ item.label }}</span>
          </a-menu-item>
        </template>
      </a-menu>
      <div class="version">v2.0.0</div>
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="topbar">
        <h2>{{ pageTitle }}</h2>
        <div class="topbar-right">
          <span class="status-dot"><span class="pulse"></span>系统运行中</span>
          <span class="clock">{{ currentTime }}</span>
          <span class="username">{{ authStore.username }}</span>
          <a-button size="small" @click="handleLogout">退出</a-button>
        </div>
      </a-layout-header>

      <a-layout-content class="content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import {
  DashboardOutlined,
  ThunderboltOutlined,
  SafetyOutlined,
  ShareAltOutlined,
  FileTextOutlined,
  FileSearchOutlined,
  TrophyOutlined,
  CheckCircleOutlined,
  BookOutlined,
  QuestionCircleOutlined,
  RobotOutlined,
  UserOutlined,
  TeamOutlined,
  AuditOutlined,
  KeyOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const collapsed = ref(false)
const selectedKeys = ref([route.name || 'Dashboard'])
const currentTime = ref('')

const allMenuItems = [
  { key: 'Dashboard', label: '工作台', icon: DashboardOutlined, permission: 'read:dashboard' },
  { key: 'Trigger', label: '触发分析', icon: ThunderboltOutlined, permission: 'write:trigger' },
  { key: 'QualityCheck', label: '质检分析', icon: SafetyOutlined, permission: 'write:quality_check' },
  { key: 'QualityResults', label: '质检结果', icon: FileSearchOutlined, permission: 'read:quality_check' },
  { key: 'Keywords', label: '关键词管理', icon: KeyOutlined, permission: 'admin:keywords' },
  { key: 'Whitelist', label: '协议话术白名单', icon: SafetyOutlined, permission: 'admin:whitelist' },
  { key: 'Referral', label: '转介绍检测', icon: ShareAltOutlined, permission: 'read:referral' },
  { key: 'Cases', label: '优秀话术提取', icon: FileTextOutlined, permission: 'read:cases' },
  { key: 'Success', label: '成功案例', icon: TrophyOutlined, permission: 'read:journey' },
  { key: 'FollowUp', label: '督学跟进合规', icon: CheckCircleOutlined, permission: 'read:followup' },
  { key: 'ScriptLib', label: '话术库', icon: BookOutlined, permission: 'read:scriptlib' },
  { key: 'Rag', label: 'RAG 问答', icon: QuestionCircleOutlined, permission: 'read:rag' },
  { key: 'Agents', label: '智能体管理', icon: RobotOutlined, permission: 'read:agents' },
  { key: 'divider-admin', label: '---', icon: null, permission: null, isDivider: true },
  { key: 'Users', label: '用户管理', icon: UserOutlined, permission: 'admin:user' },
  { key: 'Roles', label: '角色管理', icon: TeamOutlined, permission: 'admin:role' },
  { key: 'Logs', label: '日志管理', icon: AuditOutlined, permission: 'admin:logs' },
]

const visibleMenuItems = computed(() => {
  return allMenuItems.filter(item => {
    if (item.isDivider) return true
    if (!item.permission) return true
    return authStore.hasPermission(item.permission)
  })
})

const pageTitle = computed(() => {
  const item = allMenuItems.find(i => i.key === route.name)
  return item ? item.label : ''
})

function handleMenuClick({ key }) {
  const routeKey = String(key)
  if (routeKey === 'divider-admin' || routeKey.startsWith('divider')) return
  selectedKeys.value = [routeKey]
  router.push({ name: routeKey })
}

function handleLogout() {
  authStore.logout()
  router.push({ name: 'Login' })
}

watch(
  () => route.name,
  (name) => {
    if (name) selectedKeys.value = [name]
  }
)

let clockInterval
onMounted(() => {
  const update = () => {
    currentTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  update()
  clockInterval = setInterval(update, 30000)
})
onUnmounted(() => clearInterval(clockInterval))
</script>

<style scoped>
.logo {
  padding: 20px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  text-align: center;
}
.logo-icon {
  width: 32px;
  height: 32px;
  margin-bottom: 8px;
}
.logo h1 {
  color: #fff;
  font-size: 16px;
  margin: 0;
  font-weight: 600;
}
.logo p {
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
  margin: 4px 0 0;
}
.version {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
  text-align: center;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.topbar h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: #0f172a;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
  color: #64748b;
  font-size: 13px;
}
.status-dot {
  display: flex;
  align-items: center;
  gap: 6px;
}
.status-dot::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
}
.pulse {
  display: none;
}
.clock {
  font-variant-numeric: tabular-nums;
}
.username {
  color: #0f172a;
  font-weight: 500;
}
.content {
  padding: 24px;
  background: #f5f5f5;
  min-height: 280px;
}
</style>
