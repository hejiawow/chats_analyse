import request from './request'
export const getRoles = (params) => request.get('/api/roles', { params })
export const getRole = (id) => request.get(`/api/roles/${id}`)
export const createRole = (data) => request.post('/api/roles', data)
export const updateRole = (id, data) => request.put(`/api/roles/${id}`, data)
export const deleteRole = (id) => request.delete(`/api/roles/${id}`)
