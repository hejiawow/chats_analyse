import request from './request'
export const getCasesList = (params) => request.get('/api/cases', { params })
export const getCaseDetail = (id) => request.get(`/api/cases/${id}`)
export const addToRag = (id) => request.post(`/api/cases/${id}/add-to-rag`)
export const batchAddToRag = (caseIds) => request.post('/api/cases/batch-add-to-rag', { case_ids: caseIds })
