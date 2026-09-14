import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import { Skills as SkillsApi, Agents as AgentsApi } from '../api.js';
import { store } from '../store.js';
const h = htm.bind(React.createElement);

export default function Skills() {
  const [skills, setSkills] = React.useState([]);
  const [agents, setAgents] = React.useState([]);
  const [form, setForm] = React.useState({ skill_id: '', name: '', description: '', param_schema: '{}', endpoint_url: '', provider_node: '' });
  const [callForm, setCallForm] = React.useState({ agent_id: '', skill_id: '', params: '{}' });
  const [msg, setMsg] = React.useState('');

  async function load() {
    try {
      const [s, a] = await Promise.all([SkillsApi.list(), AgentsApi.list()]);
      setSkills(s.skills || []);
      setAgents(a.agents || []);
    } catch (e) { setMsg(e.message); }
  }
  React.useEffect(() => { load(); }, []);

  async function doRegister() {
    setMsg('');
    try {
      let schema = {};
      try { schema = JSON.parse(form.param_schema || '{}'); } catch (e) { setMsg('param_schema 不是合法 JSON'); return; }
      await SkillsApi.register({ ...form, param_schema: schema });
      setMsg('已注册');
      load();
      store.notify();
    } catch (e) { setMsg(e.message); }
  }

  async function doCall() {
    setMsg('');
    try {
      let params = {};
      try { params = JSON.parse(callForm.params || '{}'); } catch (e) { setMsg('params 不是合法 JSON'); return; }
      const r = await SkillsApi.call({ agent_id: callForm.agent_id, skill_id: callForm.skill_id, params });
      setMsg('工具调用已提交：' + JSON.stringify(r));
      store.notify();
    } catch (e) { setMsg(e.message); }
  }

  async function doDisable(skill_id) {
    setMsg('');
    try { await SkillsApi.disable(skill_id); setMsg('已禁用'); load(); } catch (e) { setMsg(e.message); }
  }

  return h`
  <div>
    <h2 class="page-title">🛠️ MCP-Skill 技能市场</h2>
    ${msg && h`<div class="toast">${msg}</div>`}
    <div class="card">
      <h3>注册技能</h3>
      <div class="row">
        <input placeholder="skill_id" value=${form.skill_id} onInput=${e => setForm({ ...form, skill_id: e.target.value })} />
        <input placeholder="名称" value=${form.name} onInput=${e => setForm({ ...form, name: e.target.value })} />
        <input placeholder="描述" value=${form.description} onInput=${e => setForm({ ...form, description: e.target.value })} />
        <input placeholder="param_schema JSON" value=${form.param_schema} onInput=${e => setForm({ ...form, param_schema: e.target.value })} style=${{ width: '200px' }} />
        <input placeholder="endpoint_url" value=${form.endpoint_url} onInput=${e => setForm({ ...form, endpoint_url: e.target.value })} />
        <input placeholder="provider_node" value=${form.provider_node} onInput=${e => setForm({ ...form, provider_node: e.target.value })} />
        <button onClick=${doRegister}>注册</button>
      </div>
    </div>
    <div class="card">
      <h3>调用技能（走工具审批）</h3>
      <div class="row">
        <select value=${callForm.agent_id} onChange=${e => setCallForm({ ...callForm, agent_id: e.target.value })}>
          <option value="">发起 Agent</option>
          ${agents.map(a => h`<option value=${a.agent_id} key=${a.agent_id}>${a.name} (${a.agent_id})</option>`)}
        </select>
        <select value=${callForm.skill_id} onChange=${e => setCallForm({ ...callForm, skill_id: e.target.value })}>
          <option value="">选择技能</option>
          ${skills.map(s => h`<option value=${s.skill_id} key=${s.skill_id}>${s.name} (${s.skill_id})</option>`)}
        </select>
        <input placeholder="params JSON" value=${callForm.params} onInput=${e => setCallForm({ ...callForm, params: e.target.value })} style=${{ width: '200px' }} />
        <button onClick=${doCall}>调用</button>
      </div>
    </div>
    <div class="card">
      <h3>技能列表</h3>
      <table class="table">
        <thead><tr><th>ID</th><th>名称</th><th>描述</th><th>Provider</th><th>Schema</th><th></th></tr></thead>
        <tbody>
          ${skills.map(s => h`<tr key=${s.skill_id}>
            <td>${s.skill_id}</td>
            <td>${s.name}</td>
            <td>${s.description}</td>
            <td>${s.provider_node || ''}</td>
            <td class="muted">${JSON.stringify(s.param_schema)}</td>
            <td><button class="ghost" onClick=${() => doDisable(s.skill_id)}>禁用</button></td>
          </tr>`)}
        </tbody>
      </table>
    </div>
    <button class="secondary" onClick=${load}>🔄 刷新</button>
  </div>`;
}
