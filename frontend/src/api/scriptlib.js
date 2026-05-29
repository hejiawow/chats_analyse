import request from './request'
export const getScriptLibList = (params) => request.get('/api/script-lib', { params })
export const getScriptDetail = (id) => request.get(`/api/script-lib/${id}`)
export const getScenarios = () => request.get('/api/script-lib/scenarios')
export const getScriptLibStats = () => request.get('/api/script-lib/stats')
export const getSimilarScripts = (id, params) => request.get(`/api/script-lib/similar/${id}`, { params })
