import request from './request'

// 一键审查所有未审查的高中风险结果
export const autoBatchReview = () =>
  request.post('/api/quality-review/auto-batch')

// 查询审查结果列表
export const getReviewList = (params) =>
  request.get('/api/quality-review', { params })

// 查询审查详情
export const getReviewDetail = (reviewId) =>
  request.get(`/api/quality-review/${reviewId}`)

// 编辑审查结果
export const updateReviewDetail = (reviewId, data) =>
  request.put(`/api/quality-review/${reviewId}`, data)

// 查看聊天记录（复用质检结果接口）
export const getReviewChatRecords = (resultId) =>
  request.get(`/api/quality-check/${resultId}/chat-records`)