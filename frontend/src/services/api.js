import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (token) => apiClient.post('/api/auth/login', { token }),
  me: () => apiClient.get('/api/auth/me'),
};

export const templatesAPI = {
  getAll: (channel) => apiClient.get('/api/templates', { params: { channel } }),
  create: (data) => apiClient.post('/api/templates', data),
  update: (key, data) => apiClient.put(`/api/templates/${key}`, data),
  delete: (key, channel) => apiClient.delete(`/api/templates/${key}`, { params: { channel } }),
  refreshCache: () => apiClient.post('/api/templates/cache/refresh'),
};

export const casesAPI = {
  getAll: (page, limit, status, channel) => apiClient.get('/api/cases', { params: { page, limit, status, channel } }),
  getOne: (id) => apiClient.get(`/api/cases/${id}`),
  updateStatus: (id, new_status, admin_notes) => apiClient.put(`/api/cases/${id}/status`, { new_status, admin_notes }),
};

export const dashboardAPI = {
  getStats: () => apiClient.get('/api/dashboard/stats'),
};

export const messagesAPI = {
  getAll: (page, limit, channel) => apiClient.get('/api/messages', { params: { page, limit, channel } }),
};

export const broadcastsAPI = {
  getAll: (page, limit) => apiClient.get('/api/broadcasts', { params: { page, limit } }),
  create: (data) => apiClient.post('/api/broadcasts', data),
  delete: (id) => apiClient.delete(`/api/broadcasts/${id}`),
};

export const pdfAPI = {
  getAll: () => apiClient.get('/api/pdf-templates'),
  getOne: (name) => apiClient.get(`/api/pdf-templates/${name}`),
  update: (name, data) => apiClient.put(`/api/pdf-templates/${name}`, data),
};

export const usersAPI = {
  getAll: (page, limit, search, status) => apiClient.get('/api/users', { params: { page, limit, search, status } }),
  getOne: (id) => apiClient.get(`/api/users/${id}`),
  update: (id, data) => apiClient.put(`/api/users/${id}`, data),
  ban: (id) => apiClient.post(`/api/users/${id}/ban`),
  unban: (id) => apiClient.delete(`/api/users/${id}/ban`),
};

export const casePhaseAPI = {
  advance: (caseId, data) => apiClient.put(`/api/cases/${caseId}/phase`, data),
  getHistory: (caseId) => apiClient.get(`/api/cases/${caseId}/history`),
  getEvidences: (caseId) => apiClient.get(`/api/cases/${caseId}/evidences`),
  getMessages: (caseId) => apiClient.get(`/api/cases/${caseId}/messages`),
  sendMessage: (caseId, data) => apiClient.post(`/api/cases/${caseId}/messages`, data),
  updateOverrides: (caseId, overrides) => apiClient.put(`/api/cases/${caseId}/overrides`, { overrides }),
  updateAutoPush: (caseId, data) => apiClient.put(`/api/cases/${caseId}/auto-push`, data),
  sendPersonalPush: (caseId, data) => apiClient.post(`/api/cases/${caseId}/personal-push`, data),
};

export const agentsAPI = {
  getAll: () => apiClient.get('/api/agents'),
  getInbox: (code) => apiClient.get(`/api/agents/${code}/inbox`),
};

export const adminsAPI = {
  getAll: () => apiClient.get('/api/admins'),
};

export const auditAPI = {
  getLogs: (page, limit, action_type, actor_id) => apiClient.get('/api/audit-logs', { params: { page, limit, action_type, actor_id } }),
};

export const systemAPI = {
  getConfig: () => apiClient.get('/api/system-config'),
  updateConfig: (configs) => apiClient.put('/api/system-config', { configs }),
};

export const blacklistAPI = {
  getAll: (page, limit) => apiClient.get('/api/blacklist', { params: { page, limit } }),
  add: (data) => apiClient.post('/api/blacklist', data),
  remove: (id) => apiClient.delete(`/api/blacklist/${id}`),
};

export const feeAPI = {
  getAll: () => apiClient.get('/api/fee-config'),
  update: (id, data) => apiClient.put(`/api/fee-config/${id}`, data),
};

export default apiClient;
