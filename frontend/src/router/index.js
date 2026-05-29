import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { permission: 'read:dashboard' } },
      { path: 'trigger', name: 'Trigger', component: () => import('@/views/Trigger.vue'), meta: { permission: 'write:trigger' } },
      { path: 'quality-check', name: 'QualityCheck', component: () => import('@/views/QualityCheck.vue'), meta: { permission: 'write:trigger' } },
      { path: 'quality-results', name: 'QualityResults', component: () => import('@/views/QualityResults.vue'), meta: { permission: 'read:referral' } },
      { path: 'referral', name: 'Referral', component: () => import('@/views/Referral.vue'), meta: { permission: 'read:referral' } },
      { path: 'cases', name: 'Cases', component: () => import('@/views/Cases.vue'), meta: { permission: 'read:cases' } },
      { path: 'success', name: 'Success', component: () => import('@/views/Success.vue'), meta: { permission: 'read:journey' } },
      { path: 'followup', name: 'FollowUp', component: () => import('@/views/FollowUp.vue'), meta: { permission: 'read:followup' } },
      { path: 'scriptlib', name: 'ScriptLib', component: () => import('@/views/ScriptLib.vue'), meta: { permission: 'read:scriptlib' } },
      { path: 'rag', name: 'Rag', component: () => import('@/views/Rag.vue'), meta: { permission: 'read:rag' } },
      { path: 'agents', name: 'Agents', component: () => import('@/views/Agents.vue'), meta: { permission: 'read:agents' } },
      { path: 'users', name: 'Users', component: () => import('@/views/Users.vue'), meta: { permission: 'admin:user' } },
      { path: 'roles', name: 'Roles', component: () => import('@/views/Roles.vue'), meta: { permission: 'admin:role' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.meta.requiresAuth === false) {
    if (token) return next({ name: 'Dashboard' })
    return next()
  }

  if (!token) return next({ name: 'Login' })

  if (to.meta.permission) {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      const perms = user.permissions || []
      if (!perms.includes('admin:all') && !perms.includes(to.meta.permission)) {
        return next({ name: 'Dashboard' })
      }
    } catch {}
  }

  next()
})

export default router
