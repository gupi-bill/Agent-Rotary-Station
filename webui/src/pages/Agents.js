import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import { Agents as AgentsApi } from '../api.js';
import { store } from '../store.js';
const h = htm.bind(React.createElement);

export default function Agents() {
  const [agents, setAgents] = React.useState([]);
  const [manager, setManager] = React.useState(null);
  const [msg, setMsg] = React.useState('');
  const [form, setForm] = React.useState({ agent_id: '', name: '', role: 'worker', capabilities: '', endpoint_url: '', token: '' });

  async function load() {
    try {
      const [a, m] = await Promise.all([AgentsApi.list(), AgentsApi.managerCurrent()]);
      setAgents(a.agents || []);
      setManager((m.manager) || null);
    } catch (e) { setMsg(e.message); }
  }

  React.useEffect(() => { load(); }, []);

  async function doRegister() {
    setMsg('');
    try {
      const caps = form.capabilities.split(',').map(s => s.trim()).filter(Boolean);
      await AgentsApi.register({ ...form, capabilities: caps, role: form.role || 'worker' });
      setMsg('已注册');
      await load();
      store.notify();
    } catch (e) { setMsg(e.message); }
  }

  async function doAction(action, agent_id) {
    setMsg('');
    try {
      if (action === 'heartbeat') await AgentsApi.heartbeat(agent_id);
      else if (action === 'offline') await AgentsApi.offline(agent_id);
      else if (action === 'manager') await AgentsApi.managerSet(agent_id);
      setMsg('已执行');
      await load();
      store.notify();
    } catch (e) { setMsg(e.message); }
  }

  async function clearManager() {
    setMsg('');
    try { await AgentsApi.managerClear(); await load(); store.notify(); } catch (e) { setMsg(e.message); }
  }

  return h`
  <div>
    <h2 class="page-title">🤖 Agent 管理</h2>
    ${msg && h`<div class="toast">${msg}</div>`}
    <div class="card">
      <h3>管理岗</h3>
      <div class="row">
        ${manager
          ? h`<span class="chip">${manager.name} (${manager.agent_id})</span>`
          : h`<span class="dim">暂无管理岗</span>`}
        <button class="secondary" onClick=${clearManager} disabled=${!manager}>撤销管理岗</button>
      </div>
    </div>
    <div class="card">
      <h3>注册新 Agent</h3>
      <div class="row">
        <input placeholder="agent_id" value=${form.agent_id} onInput=${e => setForm({ ...form, agent_id: e.target.value })} />
        <input placeholder="名称" value=${form.name} onInput=${e => setForm({ ...form, name: e.target.value })} />
        <select value=${form.role} onChange=${e => setForm({ ...form, role: e.target.value })}>
          <option value="worker">worker</option>
          <option value="toolnode">toolnode</option>
        </select>
        <input placeholder="能力标签，逗号分隔" value=${form.capabilities} onInput=${e => setForm({ ...form, capabilities: e.target.value })} style=${{ minWidth: '180px' }} />
        <input placeholder="endpoint_url（可空）" value=${form.endpoint_url} onInput=${e => setForm({ ...form, endpoint_url: e.target.value })} />
        <button onClick=${doRegister}>注册</button>
      </div>
    </div>
    <div class="card">
      <h3>Agent 列表</h3>
      <table class="table">
        <thead><tr><th>ID</th><th>名称</th><th>角色</th><th>状态</th><th>能力</th><th>操作</th></tr></thead>
        <tbody>
          ${agents.map(a => h`<tr key=${a.agent_id}>
            <td>${a.agent_id}</td>
            <td>${a.name}</td>
            <td>${a.role}</td>
            <td class=${a.status === 'online' ? 'ok' : 'dim'}>${a.status}</td>
            <td>${(a.capabilities || []).map(c => h`<span class="chip" key=${c}>${c}</span>`)}</td>
            <td class="row">
              <button class="ghost" onClick=${() => doAction('heartbeat', a.agent_id)}>心跳</button>
              <button class="ghost" onClick=${() => doAction('offline', a.agent_id)}>下线</button>
              <button class="ghost" onClick=${() => doAction('manager', a.agent_id)}>设管理岗</button>
            </td>
          </tr>`)}
        </tbody>
      </table>
    </div>
    <button class="secondary" onClick=${load}>🔄 刷新</button>
  </div>`;
}
