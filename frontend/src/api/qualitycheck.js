import request from './request'

// 触发质检分析
export const triggerQualityCheck = (data) =>
  request.post('/api/trigger/quality-check', data)

// 获取质检结果列表
export const getQualityCheckList = (params) =>
  request.get('/api/quality-check', { params })

// 获取质检结果详情
export const getQualityCheckDetail = (id) =>
  request.get(`/api/quality-check/${id}`)

// 获取关键词列表
export const getKeywordList = (params) =>
  request.get('/api/keywords', { params })

// 添加关键词
export const addKeyword = (data) =>
  request.post('/api/keywords', data)

// 更新关键词
export const updateKeyword = (id, data) =>
  request.put(`/api/keywords/${id}`, data)

// 删除关键词
export const deleteKeyword = (id) =>
  request.delete(`/api/keywords/${id}`)

// 初始化默认关键词
export const initDefaultKeywords = () =>
  request.post('/api/keywords/init-default')

// 获取任务日志
export const getLogs = (taskId) =>
  request.get(`/api/logs/${taskId}`)

// === 批量质检相关 ===

// 获取组织架构
export const getOrganization = () =>
  request.get('/api/organization')

// 触发批量质检
export const triggerBatchQualityCheck = (data) =>
  request.post('/api/trigger/batch-quality-check', data)

// data: { start_time, end_time, user_id, limit }

// 获取批量质检进度
export const getBatchProgress = (taskId) =>
  request.get(`/api/batch-quality-check/${taskId}/progress`)

// 获取批量质检失败详情
export const getBatchErrors = (taskId) =>
  request.get(`/api/batch-quality-check/${taskId}/errors`)

// 取消批量质检任务
export const cancelBatchQualityCheck = (taskId) =>
  request.post(`/api/batch-quality-check/${taskId}/cancel`)

// 触发新批量质检（基于聊天记录关键词匹配）
export const triggerBatchQualityCheckByMessages = (data) =>
  request.post('/api/trigger/batch-quality-check-by-messages', data)

// 获取质检统计数据（支持筛选参数，但风险等级筛选不影响统计）
export const getQualityCheckStats = (params) =>
  request.get('/api/quality-check/stats', { params })

// 导出质检结果 CSV
export const exportQualityCheckResults = (params) =>
  request.get('/api/quality-check/export', { params, responseType: 'blob' })

// 获取质检结果对应的聊天记录
export const getQualityCheckChatRecords = (resultId) =>
  request.get(`/api/quality-check/${resultId}/chat-records`)

// 获取销售列表
export const getSalesList = () =>
  request.get('/api/sales')

// 获取好友列表
export const getFriendsList = (user_id) =>
  request.get(`/api/friends/${user_id}`)

// 获取启用的关键词列表（用于筛选下拉框）
export const getActiveKeywords = () =>
  request.get('/api/keywords/active')

// 批量获取好友列表
export const getFriendsBatch = (user_ids) =>
  request.post('/api/friends/batch', { user_ids })