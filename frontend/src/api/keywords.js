import request from './request'

// 获取关键词统计数据
export const getKeywordStats = () => request.get('/api/keywords/stats')

// 获取启用的关键词列表（用于下拉筛选）
export const getActiveKeywords = () => request.get('/api/keywords/active')

// 获取关键词列表（管理员）
export const getKeywords = (params) => request.get('/api/keywords', { params })

// 添加关键词
export const createKeyword = (data) => request.post('/api/keywords', data)

// 更新关键词
export const updateKeyword = (id, data) => request.put(`/api/keywords/${id}`, data)

// 删除关键词
export const deleteKeyword = (id) => request.delete(`/api/keywords/${id}`)

// 初始化默认关键词
export const initDefaultKeywords = () => request.post('/api/keywords/init-default')