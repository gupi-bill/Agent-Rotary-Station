import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import { Messages as MsgApi, Agents as AgentsApi, Tasks as TasksApi } from '../api.js';
const h = htm.bind(React.createElement);

export default function Chat() {
  const [messages, setMessages] = React.useState([]);
  const [agents, setAgents] = React.useState([]);
  const [tasks, setTasks] = React.useState([]);
  const [form, setForm] = React.useState({ from_agent: '', channel_type: 'private', to_agent: '', task_id: '', content: '' });
  const [msg, setMsg] = React.useState('');

  async function loadMeta() {
    try {
      const [a, t] = await Promise.all([AgentsApi.list(), TasksApi.list()]);
      setAgents(a.agents || []);
      setTasks(t.tasks || []);
    } catch (e) { setMsg(e.message); }
  }
  async function loadHistory() {
    try {
      const params = { limit: 100 };
      if (form.channel_type) params.channel_type = form.channel_type;
      if (form.task_id) params.task_id = form.task_id;
      if (form.to_agent) params.to_agent = form.to_agent;
      if (form.from_agent) params.from_agent = form.from_agent;
      const r = await MsgApi.history(params);
      setMessages(r.messages || []);
    } catch (e) { setMsg(e.message); }
  }
  React.useEffect(() => { loadMeta(); loadHistory(); }, []);

  async function send() {
    setMsg('');
    try {
      await MsgApi.send(form);
      setMsg('已发送');
      loadHistory();
    } catch (e) { setMsg(e.message); }
  }

  return h`
  <div>
    <h2 class="page-title">💬 Agent 通讯</h2>
    ${msg && h`<div class="toast">${msg}</div>`}
    <div class="card">
      <h3>发消息</h3>
      <div class="row">
        <select value=${form.from_agent} onChange=${e => setForm({ ...form, from_agent: e.target.value })}>
          <option value="">from_agent</option>
          ${agents.map(a => h`<option value=${a.agent_id} key=${a.agent_id}>${a.name} (${a.agent_id})</option>`)}
        </select>
        <select value=${form.channel_type} onChange=${e => setForm({ ...form, channel_type: e.target.value })}>
          <option value="private">private</option>
          <option value="group">group</option>
          <option value="task">task</option>
        </select>
        <select value=${form.to_agent} onChange=${e => setForm({ ...form, to_agent: e.target.value })}>
          <option value="">to_agent（可空）</option>
          ${agents.map(a => h`<option value=${a.agent_id} key=${a.agent_id}>${a.name} (${a.agent_id})</option>`)}
        </select>
        <select value=${form.task_id} onChange=${e => setForm({ ...form, task_id: e.target.value })}>
          <option value="">task_id（可空）</option>
          ${tasks.map(t => h`<option value=${t.task_id} key=${t.task_id}>${t.title} (${t.task_id})</option>`)}
        </select>
        <input placeholder="内容" value=${form.content} onInput=${e => setForm({ ...form, content: e.target.value })} style=${{ flex: 1 }} />
        <button onClick=${send}>发送</button>
        <button class="secondary" onClick=${loadHistory}>刷新</button>
      </div>
    </div>
    <div class="card">
      <h3>消息历史</h3>
      <table class="table">
        <thead><tr><th>时间</th><th>频道</th><th>From</th><th>To</th><th>Task</th><th>内容</th></tr></thead>
        <tbody>
          ${messages.map(m => h`<tr key=${m.msg_id || m.id}>
            <td class="muted">${m.created_at}</td>
            <td>${m.channel_type}</td>
            <td>${m.from_agent}</td>
            <td>${m.to_agent || ''}</td>
            <td>${m.task_id || ''}</td>
            <td>${m.content}</td>
          </tr>`)}
        </tbody>
      </table>
    </div>
  </div>`;
}
