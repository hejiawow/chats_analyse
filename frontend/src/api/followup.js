import request from './request'
export const getFollowUpList = (params) => request.get('/api/follow-up', { params })
export const getFollowUpDetail = (id) => request.get(`/api/follow-up/${id}`)
