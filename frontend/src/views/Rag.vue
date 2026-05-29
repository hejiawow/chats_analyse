<template>
  <div class="page-card rag-chat">
    <div class="chat-header">
      <h3>RAG 问答</h3>
    </div>

    <!-- Chat messages area -->
    <div class="chat-container" ref="chatContainer">
      <!-- Welcome message when no messages yet -->
      <div v-if="messages.length === 0" class="welcome">
        <div class="welcome-icon">💬</div>
        <p>你好，我是虎鲸智能助手，有什么可以帮你的吗？</p>
      </div>

      <!-- Message list -->
      <div v-for="(msg, idx) in messages" :key="idx" :class="['message-row', msg.role === 'user' ? 'message-user' : 'message-bot']">
        <div class="message-bubble" :class="msg.role === 'user' ? 'bubble-user' : 'bubble-bot'">
          <span v-if="msg.role === 'user'">{{ msg.content }}</span>
          <template v-else>
            <div v-if="msg.loading" class="loading-dots">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
            <div v-else>
              <div class="bot-content" v-html="msg.formattedContent"></div>
              <!-- Sources section -->
              <div v-if="msg.sources && msg.sources.length" class="sources-section">
                <div class="sources-label">参考来源 ({{ msg.sources.length }} 个案例)</div>
                <div class="sources-list">
                  <a-tag
                    v-for="(src, si) in msg.sources"
                    :key="si"
                    color="blue"
                    class="source-tag"
                    @click="showSourceDetail(src)"
                  >
                    {{ src.scenario_type || '未知场景' }}
                  </a-tag>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Input area -->
    <div class="chat-input-area">
      <a-textarea
        v-model:value="inputText"
        placeholder="输入问题，基于话术库回答问题..."
        :auto-size="{ minRows: 1, maxRows: 3 }"
        @keydown="handleKeyDown"
        class="chat-input"
      />
      <a-button type="primary" @click="send" :loading="sending" :disabled="!inputText.trim()">
        发送
      </a-button>
    </div>

    <!-- Source detail modal -->
    <a-modal v-model:open="sourceDetailVisible" title="话术详情" width="700px" :footer="null">
      <div v-if="sourceDetail">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="销售ID">{{ sourceDetail.user_id }}</a-descriptions-item>
          <a-descriptions-item label="好友ID">{{ sourceDetail.friend_id }}</a-descriptions-item>
          <a-descriptions-item label="好友昵称">{{ sourceDetail.friend_nick || '-' }}</a-descriptions-item>
          <a-descriptions-item label="场景类型">{{ sourceDetail.scenario_type || '-' }}</a-descriptions-item>
        </a-descriptions>

        <div style="margin-top: 16px">
          <div v-if="sourceDetail.customer_question" style="padding: 8px 12px; background: #f8fafc; border-radius: 6px; margin-bottom: 8px; font-size: 13px">
            <strong>客户问题：</strong>{{ sourceDetail.customer_question }}
          </div>
          <div v-if="sourceDetail.sales_answer" style="padding: 12px; background: #fef2f2; border-left: 3px solid #ef4444; border-radius: 6px; font-size: 14px; line-height: 1.6">
            <strong>销冠回答：</strong>{{ sourceDetail.sales_answer }}
          </div>
        </div>

        <div v-if="sourceDetail.core_design_logic" style="margin-top: 16px">
          <h4 style="margin-bottom: 8px; font-size: 15px; color: #10b981">话术拆解</h4>
          <div style="padding: 12px; background: #f0fdf4; border-radius: 6px; font-size: 14px; line-height: 1.6">
            <strong>核心设计逻辑：</strong>{{ sourceDetail.core_design_logic }}
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { ragAsk } from '@/api/rag'
import { getScriptDetail } from '@/api/scriptlib'

const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const chatContainer = ref(null)

const sourceDetailVisible = ref(false)
const sourceDetail = ref(null)

function formatBotContent(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

async function send() {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  inputText.value = ''
  sending.value = true

  // Add user message
  messages.value.push({ role: 'user', content: text })
  scrollToBottom()

  // Add loading bot message
  const loadingIdx = messages.value.length
  messages.value.push({ role: 'bot', loading: true })
  scrollToBottom()

  try {
    const res = await ragAsk(text)
    // Remove loading message
    messages.value.splice(loadingIdx, 1)

    // Add bot response
    const answer = res.answer || res.data?.answer || '抱歉，没有找到相关信息。'
    const sources = res.sources || res.data?.sources || []

    messages.value.push({
      role: 'bot',
      formattedContent: formatBotContent(answer),
      sources: sources
    })
  } catch {
    messages.value.splice(loadingIdx, 1)
    messages.value.push({
      role: 'bot',
      formattedContent: '请求失败，请稍后重试。'
    })
  }

  sending.value = false
  scrollToBottom()
}

function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.ctrlKey) {
    e.preventDefault()
    send()
  }
}

async function showSourceDetail(source) {
  try {
    sourceDetail.value = await getScriptDetail(source.id)
    sourceDetailVisible.value = true
  } catch {
    sourceDetail.value = null
    sourceDetailVisible.value = true
  }
}
</script>

<style scoped>
.rag-chat {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  padding: 0;
  overflow: hidden;
}

.chat-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.chat-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: #94a3b8;
  font-size: 15px;
}

.welcome-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.message-row {
  display: flex;
  width: 100%;
}

.message-user {
  justify-content: flex-end;
}

.message-bot {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.bubble-user {
  background: #6366f1;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble-bot {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 4px;
}

.loading-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
  animation: bounce 1.2s infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.bot-content {
  margin-bottom: 8px;
}

.sources-section {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #e2e8f0;
}

.sources-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}

.sources-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.source-tag {
  cursor: pointer;
}

.chat-input-area {
  display: flex;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid #e2e8f0;
  align-items: flex-end;
}

.chat-input {
  flex: 1;
}

.chat-input :deep(.ant-input) {
  border-radius: 8px;
  resize: none;
}
</style>
