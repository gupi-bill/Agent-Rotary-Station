// api.js —— 统一 fetch 封装，前端只调用后端 REST API，不直连数据库。
export async function api(path, opts = {}) {
  const init = { ...opts };
  if (opts.body != null) {
    init.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  }
  const res = await fetch(path, init);
  let data = null;
  const text = await res.text();
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  if (!res.ok && data && data.detail) {
    const err = new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
    err.status = res.status;
    err.detail = data.detail;
    throw err;
  }
  return data;
}

export const Agents = {
  list: () => api('/agents'),
  register: (body) => api('/agents/register', { method: 'POST', body: JSON.stringify(body) }),
  heartbeat: (agent_id) => api('/agents/heartbeat', { method: 'POST', body: JSON.stringify({ agent_id }) }),
  offline: (agent_id) => api('/agents/offline', { method: 'POST', body: JSON.stringify({ agent_id }) }),
  update: (agent_id, body) => api(`/agents/${agent_id}/update`, { method: 'POST', body: JSON.stringify(body) }),
  managerSet: (agent_id) => api('/agents/manager/set', { method: 'POST', body: JSON.stringify({ agent_id }) }),
  managerCurrent: () => api('/agents/manager/current'),
  managerClear: () => api('/agents/manager/clear', { method: 'POST' }),
};

export const Tasks = {
  list: () => api('/tasks'),
  detail: (id) => api(`/tasks/${id}`),
  create: (body) => api('/tasks/create', { method: 'POST', body: JSON.stringify(body) }),
  broadcast: (body) => api('/tasks/broadcast', { method: 'POST', body: JSON.stringify(body) }),
  assign: (body) => api('/tasks/assign', { method: 'POST', body: JSON.stringify(body) }),
  status: (body) => api('/tasks/status', { method: 'POST', body: JSON.stringify(body) }),
  members: (id) => api(`/tasks/${id}/members`),
};

export const Messages = {
  send: (body) => api('/messages/send', { method: 'POST', body: JSON.stringify(body) }),
  history: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api('/messages/history' + (qs ? '?' + qs : ''));
  },
  taskChannel: (task_id) => api(`/messages/task/${task_id}`),
};

export const Memories = {
  write: (body) => api('/memories/write', { method: 'POST', body: JSON.stringify(body) }),
  delete: (body) => api('/memories/delete', { method: 'POST', body: JSON.stringify(body) }),
  decide: (body) => api('/memories/approvals/decide', { method: 'POST', body: JSON.stringify(body) }),
  pending: () => api('/memories/approvals/pending'),
  read: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api('/memories/read' + (qs ? '?' + qs : ''));
  },
  listDomains: (reader) => api(`/memories/list-domains?reader=${encodeURIComponent(reader)}`),
};

export const Skills = {
  list: () => api('/skills'),
  get: (skill_id) => api(`/skills/${skill_id}`),
  register: (body) => api('/skills/register', { method: 'POST', body: JSON.stringify(body) }),
  disable: (skill_id) => api(`/skills/${skill_id}/disable`, { method: 'POST' }),
  call: (body) => api('/skills/call', { method: 'POST', body: JSON.stringify(body) }),
};

export const Tools = {
  call: (body) => api('/tools/call', { method: 'POST', body: JSON.stringify(body) }),
  decide: (body) => api('/tools/approvals/decide', { method: 'POST', body: JSON.stringify(body) }),
  queuePending: () => api('/tools/queue/pending'),
  requestsPending: () => api('/tools/requests/pending'),
  request: (request_id) => api(`/tools/requests/${request_id}`),
  queueProcess: () => api('/tools/queue/process', { method: 'POST' }),
};

export const System = {
  health: () => api('/system/health'),
  auditLogs: (limit = 100) => api(`/system/audit-logs?limit=${limit}`),
  emergencyBlock: () => api('/system/emergency-block'),
  toggleBlock: (active) => api(`/system/emergency-block/toggle?active=${active}`, { method: 'POST' }),
  heartbeatCheck: () => api('/system/heartbeat-check', { method: 'POST' }),
  toolQueueProcess: () => api('/system/tool-queue/process', { method: 'POST' }),
};

export const Workflows = {
  list: () => api('/workflows'),
  get: (id) => api(`/workflows/${id}`),
  create: (body) => api('/workflows/create', { method: 'POST', body: JSON.stringify(body) }),
  update: (id, body) => api(`/workflows/${id}/update`, { method: 'POST', body: JSON.stringify(body) }),
  del: (id) => api(`/workflows/${id}/delete`, { method: 'POST' }),
  run: (id, trigger_by = 'human') => api(`/workflows/${id}/run?trigger_by=${trigger_by}`, { method: 'POST' }),
  runStatus: (run_id) => api(`/workflows/runs/${run_id}`),
  runs: (id) => api(`/workflows/${id}/runs`),
  approveRun: (run_id, manager_id = 'human') => api(`/workflows/runs/${run_id}/approve?manager_id=${manager_id}`, { method: 'POST' }),
  denyRun: (run_id, manager_id = 'human') => api(`/workflows/runs/${run_id}/deny?manager_id=${manager_id}`, { method: 'POST' }),
};
