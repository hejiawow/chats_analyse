<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <img src="/assets/favicon.svg" alt="logo" class="login-logo" />
        <h1>AI会话分析平台</h1>
        <p>销售合规分析平台</p>
      </div>
      <a-form :model="form" :rules="rules" @finish="handleLogin" layout="vertical">
        <a-form-item name="username">
          <a-input v-model:value="form.username" placeholder="请输入用户名" size="large" :prefix="h(UserOutlined)">
          </a-input>
        </a-form-item>
        <a-form-item name="password">
          <a-input-password v-model:value="form.password" placeholder="请输入密码" size="large" :prefix="h(LockOutlined)">
          </a-input-password>
        </a-form-item>
        <a-form-item>
          <a-alert v-if="errorMsg" :message="errorMsg" type="error" show-icon closable @close="errorMsg = ''" style="margin-bottom: 16px" />
          <a-button type="primary" html-type="submit" size="large" block :loading="loading">
            登 录
          </a-button>
        </a-form-item>
      </a-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, h } from 'vue'
import { useRouter } from 'vue-router'
import { UserOutlined, LockOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/store/auth'
import { message } from 'ant-design-vue'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  loading.value = true
  errorMsg.value = ''
  try {
    await authStore.login(form.username, form.password)
    message.success('登录成功')
    router.push({ name: 'Dashboard' })
  } catch (err) {
    errorMsg.value = err.message || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
}
.login-card {
  width: 400px;
  background: #fff;
  border-radius: 16px;
  padding: 40px 32px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}
.login-header {
  text-align: center;
  margin-bottom: 32px;
}
.login-logo {
  width: 48px;
  height: 48px;
  margin-bottom: 12px;
}
.login-header h1 {
  font-size: 22px;
  color: #0f172a;
  margin: 0;
  font-weight: 700;
}
.login-header p {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0 0;
}
</style>
