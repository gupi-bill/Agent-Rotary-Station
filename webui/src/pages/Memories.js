import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import { Memories as MemApi, Agents as AgentsApi } from '../api.js';
import { store } from '../store.js';
const h = htm.bind(React.createElement);

export default function Memories() {
  const [domains, setDomains] = React.useState([]);
  const [entries, setEntries] = React.useState([]);
  const [agents, setAgents] = React.useState([]);
  const [form, setForm] = React.useState({ agent_id: '', domain: 'global', mem_key: '', content: '' });
  const [query, setQuery] = React.useState({ reader: '', domain: '', mem_key: '' });
  const [msg, setMsg] = React.useState('');

  async function loadAgents() {
    try { const a = await AgentsApi.list(); setAgents(a.agents || []); } catch {}
  }
  async function loadDomains() {
    if (!query.reader) return;
    try {
      const r = await MemApi.listDomains(query.reader);
      setDomains(r.domains || r.entries || []);
    } catch (e) { setMsg(e.message); }
  }
  async function loadEntries() {
    try {
      const params = {};
      if (query.reader) params.reader = query.reader;
      if (query.domain) params.domain = query.domain;
      if (query.mem_key) params.mem_key = query.mem_key;
      const r = await MemApi.read(params);
      setEntries(r.entries || r.memories || []);
    } catch (e) { setMsg(e.message); }
  }
  React.useEffect(() => { loadAgents(); }, []);

  async function doWrite() {
    setMsg('');
    try {
      const r = await MemApi.write(form);
      setMsg('写记忆已提交：' + JSON.stringify(r));
      store.notify();
    } catch (e) { setMsg(e.message); }
  }

  async function doDelete(entry) {
    setMsg('');
    try {
      const r = await MemApi.delete({ agent_id: form.agent_id || query.reader || 'human', domain: entry.domain, mem_key: entry.mem_key });
      setMsg('删除已提交：' + JSON.stringify(r));
      store.notify();
    } catch (e) { setMsg(e.message); }
  }

  return h`
  <div>
    <h2 class="page-title">🧠 三层记忆池</h2>
    ${msg && h`<div class="toast">${msg}</div>`}
    <div class="card">
      <h3>写记忆（需管理岗审批）</h3>
      <div class="row">
        <select value=${form.agent_id} onChange=${e => setForm({ ...form, agent_id: e.target.value })}>
          <option value="">选择发起 Agent</option>
          ${agents.map(a => h`<option value=${a.agent_id} key=${a.agent_id}>${a.name} (${a.agent_id})</option>`)}
        </select>
        <input placeholder="domain: global / agent:id / task:id" value=${form.domain} onInput=${e => setForm({ ...form, domain: e.target.value })} />
        <input placeholder="mem_key" value=${form.mem_key} onInput=${e => setForm({ ...form, mem_key: e.target.value })} />
        <input placeholder="内容" value=${form.content} onInput=${e => setForm({ ...form, content: e.target.value })} style=${{ flex: 1 }} />
        <button onClick=${doWrite}>提交写记忆</button>
      </div>
    </div>
    <div class="card">
      <h3>查询记忆</h3>
      <div class="row">
        <input placeholder="reader（agent_id）" value=${query.reader} onInput=${e => setQuery({ ...query, reader: e.target.value })} />
        <input placeholder="domain（可空）" value=${query.domain} onInput=${e => setQuery({ ...query, domain: e.target.value })} />
        <input placeholder="mem_key（可空）" value=${query.mem_key} onInput=${e => setQuery({ ...query, mem_key: e.target.value })} />
        <button class="secondary" onClick=${loadDomains}>查看域</button>
        <button onClick=${loadEntries}>查询</button>
      </div>
      <div class="row" style=${{ marginTop: '8px' }}>
        ${domains.map(d => h`<span class="chip" key=${JSON.stringify(d)}>${typeof d === 'string' ? d : JSON.stringify(d)}</span>`)}
      </div>
      <table class="table">
        <thead><tr><th>domain</th><th>key</th><th>content</th><th>owner</th><th></th></tr></thead>
        <tbody>
          ${entries.map(en => h`<tr key=${en.domain + ':' + en.mem_key}>
            <td>${en.domain}</td>
            <td>${en.mem_key}</td>
            <td>${en.content}</td>
            <td>${en.owner_agent || ''}</td>
            <td><button class="ghost" onClick=${() => doDelete(en)}>删</button></td>
          </tr>`)}
        </tbody>
      </table>
    </div>
  </div>`;
}
