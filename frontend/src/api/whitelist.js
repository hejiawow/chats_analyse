import request from './request'

// 获取协议话术白名单列表
export const getWhitelistPatterns = () => request.get('/api/refund-whitelist')

// 新增协议话术
export const createWhitelistPattern = (data) => request.post('/api/refund-whitelist', data)

// 更新协议话术
export const updateWhitelistPattern = (id, data) => request.put(`/api/refund-whitelist/${id}`, data)

// 删除协议话术
export const deleteWhitelistPattern = (id) => request.delete(`/api/refund-whitelist/${id}`)

// 启用/禁用协议话术
export const toggleWhitelistPattern = (id) => request.put(`/api/refund-whitelist/${id}/toggle`)