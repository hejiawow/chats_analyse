import request from './request'
export const ragAsk = (query, topK = 5) => request.post('/api/rag/ask', { query, top_k: topK })
