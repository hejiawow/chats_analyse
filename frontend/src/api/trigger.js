import request from './request'
export const triggerAll = (data) => request.post('/api/trigger', data)
export const triggerSingle = (data) => request.post('/api/trigger/single', data)
export const triggerSalesJourney = (data) => request.post('/api/trigger/sales-journey', data)
export const getLogs = (taskId) => request.get(`/api/logs/${taskId}`)
export const clearLogs = (taskId) => request.post(`/api/logs/${taskId}/clear`)
export const getDatasources = () => request.get('/api/datasources')
