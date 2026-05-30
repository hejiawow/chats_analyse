import request from './request'

// 获取日志列表
export const getLogs = (params) => request.get('/api/logs', { params })

// 获取日志统计
export const getLogStatistics = (params) => request.get('/api/logs/statistics', { params })

// 获取我的操作日志
export const getMyLogs = (params) => request.get('/api/logs/my-actions', { params })

// 清理旧日志
export const deleteOldLogs = (days) => request.delete(`/api/logs/old?days=${days}`)