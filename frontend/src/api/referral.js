import request from './request'
export const getReferralList = (params) => request.get('/api/referral', { params })
export const getReferralDetail = (id) => request.get(`/api/referral/${id}`)
