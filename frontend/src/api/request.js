import axios from 'axios'
import { message } from 'ant-design-vue'

const request = axios.create({
  baseURL: '',
  timeout: 120000,  // 2 minutes - AI calls can take long time
})

// Request interceptor: attach JWT token
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: handle errors globally
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
        return Promise.reject(new Error('登录已过期'))
      }
      if (status === 403) {
        message.error(data.detail || '权限不足')
        return Promise.reject(new Error('权限不足'))
      }
      const msg = data.detail || `请求失败 (${status})`
      message.error(msg)
      return Promise.reject(new Error(msg))
    }
    message.error('网络错误，请检查网络连接')
    return Promise.reject(error)
  }
)

export default request
