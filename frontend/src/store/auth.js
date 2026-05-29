import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')

  let parsedUser = {}
  try {
    parsedUser = JSON.parse(localStorage.getItem('user') || '{}')
  } catch {}
  const user = ref(parsedUser)

  const isLoggedIn = computed(() => !!token.value)
  const username = computed(() => user.value.username || '')
  const permissions = computed(() => user.value.permissions || [])

  function hasPermission(perm) {
    return permissions.value.includes('admin:all') || permissions.value.includes(perm)
  }

  function setAuth(data) {
    token.value = data.access_token
    user.value = {
      user_id: data.user_id,
      username: data.username,
      email: data.email,
      role_names: data.role_names,
      permissions: data.permissions,
    }
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  async function login(usernameVal, password) {
    const request = (await import('@/api/request')).default
    const data = await request.post('/api/auth/login', { username: usernameVal, password })
    setAuth(data)
    return data
  }

  function logout() {
    token.value = ''
    user.value = {}
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, username, permissions, hasPermission, setAuth, login, logout }
})
