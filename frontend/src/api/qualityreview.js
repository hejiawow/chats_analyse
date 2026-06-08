import request from './request'

// 单条即时审查
export const instantReview = (resultId) =>
  request.post(`/api/quality-review/instant/${resultId}`)

// 批量异步审查
export const batchReview = (resultIds) =>
  request.post('/api/quality-review/batch', { result_ids: resultIds })

// 查询审查结果列表
export const getReviewList = (params) =>
  request.get('/api/quality-review', { params })

// 查询审查详情
export const getReviewDetail = (reviewId) =>
  request.get(`/api/quality-review/${reviewId}`)