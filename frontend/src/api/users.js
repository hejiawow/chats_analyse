import request from './request'
export const getUsers = (params) => request.get('/api/users', { params })
export const getUser = (id) => request.get(`/api/users/${id}`)
export const createUser = (data) => request.post('/api/users', data)
export const updateUser = (id, data) => request.put(`/api/users/${id}`, data)
export const deleteUser = (id) => request.delete(`/api/users/${id}`)
export const assignRoles = (userId, roleIds) => request.post(`/api/users/${userId}/roles`, { role_ids: roleIds })
