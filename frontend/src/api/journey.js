import request from './request'
export const getSalesJourneys = (params) => request.get('/api/sales-journeys', { params })
export const getSalesJourneyDetail = (id) => request.get(`/api/sales-journeys/${id}`)
export const getDatasources = () => request.get('/api/datasources')
