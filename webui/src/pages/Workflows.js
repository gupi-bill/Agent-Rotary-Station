// Workflows.js —— 工作流列表：创建入口、运行、编辑、查看 run、删除。
import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import { Workflows } from '../api.js';
import { store } from '../store.js';
const h = htm.bind(React.createElement);

export default function Workflows({ onOpenEditor }) {
  const [items, setItems] = React.useState([]);
  const [msg, setMsg] = React.useState('');
  const [form, setForm] = React.useState({ name: '', description: '' });
  const [runs, setRuns] = React.useState({}); // workflow_id -> runs[]

  async function load() {
    setMsg('');
    try {
      const r = await Workflows.list();
      setItems(r.workflows || []);
    } catch (e) { setMsg(e.message); }
  }
  React.useEffect(() => {
    load();
    const un = store.subscribe(load);
    return un;
  }, []);

  async function createWf() {
    setMsg('');
    if (!form.name.trim()) { setMsg('请填写工作流名称'); return; }
    try {
      const r = await Workflows.create({
        name: form.name.trim(),
        description: form.description,
        definition: { nodes: [], edges: [] },
      });
      setForm({ name: '', description: '' });
      await load();
      if (r && r.workflow_id && onOpenEditor) onOpenEditor(r.workflow_id);
    } catch (e) { setMsg(e.message); }
  }

  async function runWf(id) {
    setMsg('');
    try {
      const r = await Workflows.run(id);
      setMsg('已触发：' + (r.run_id || JSON.stringify(r)));
      await loadRuns(id);
      await load();
    } catch (e) { setMsg(e.message); }
  }

  async function delWf(id) {
    if (!confirm('确认删除工作流 ' + id + ' ？')) return;
    setMsg('');
    try {
      await Workflows.del(id);
      await load();
    } catch (e) { setMsg(e.message); }
  }

  async function loadRuns(id) {
    try {
      const r = await Workflows.runs(id);
      setRuns(prev => ({ ...prev, [id]: r.runs || r.run_list || [] }));
    } catch (e) { setMsg(e.message); }
  }

  async function approveRun(runId) {
    try { await Workflows.approveRun(runId); setMsg('已批准 run ' + runId); await load(); }
    catch (e) { setMsg(e.message); }
  }
  async function denyRun(runId) {
    try { await Workflows.denyRun(runId); setMsg('已拒绝 run ' + runId); await load(); }
    catch (e) { setMsg(e.message); }
  }

  return h`
  <div>
    <h2 class="page-title">🔀 工作流</h2>
    ${msg && h`<div class="toast">${msg}</div>`}
    <div class="card">
      <h3>新建工作流</h3>
      <div class="row">
        <input placeholder="名称" value=${form.name} onInput=${e => setForm({ ...form, name: e.target.value })} />
        <input placeholder="描述（可空）" value=${form.description} onInput=${e => setForm({ ...form, description: e.target.value })} style=${{ minWidth: '260px' }} />
        <button onClick=${createWf}>＋ 创建并编辑</button>
      </div>
    </div>
    <div class="card">
      <h3>工作流列表</h3>
      <table class="table">
        <thead><tr><th>ID</th><th>名称</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          ${items.map(w => h`<tr key=${w.workflow_id}>
            <td>${w.workflow_id}</td>
            <td>${w.name}</td>
            <td class=${w.status === 'active' ? 'ok' : 'dim'}>${w.status}</td>
            <td class="row">
              <button class="ghost" onClick=${() => onOpenEditor(w.workflow_id)}>✏️ 编辑</button>
              <button class="ghost" onClick=${() => runWf(w.workflow_id)}>▶ 运行</button>
              <button class="ghost" onClick=${() => loadRuns(w.workflow_id)}>📜 run</button>
              <button class="ghost danger" onClick=${() => delWf(w.workflow_id)}>🗑 删除</button>
            </td>
          </tr>`)}
          ${items.length === 0 && h`<tr><td colspan=4 class="dim">暂无工作流</td></tr>`}
        </tbody>
      </table>
    </div>
    ${Object.entries(runs).map(([id, list]) => h`
      <div class="card" key=${'runs_' + id}>
        <h3>run 记录 · ${id}</h3>
        <table class="table">
          <thead><tr><th>run_id</th><th>状态</th><th>当前节点</th><th>操作</th></tr></thead>
          <tbody>
            ${list.map(r => h`<tr key=${r.run_id}>
              <td>${r.run_id}</td>
              <td class=${r.status === 'done' ? 'ok' : r.status === 'failed' ? 'err' : 'warn'}>${r.status}</td>
              <td>${r.current_node || '-'}</td>
              <td class="row">
                ${r.status === 'awaiting_approval' && h`
                  <button class="ghost" onClick=${() => approveRun(r.run_id)}>✅ 批准</button>
                  <button class="ghost danger" onClick=${() => denyRun(r.run_id)}>❌ 拒绝</button>`}
              </td>
            </tr>`)}
            ${list.length === 0 && h`<tr><td colspan=4 class="dim">暂无 run</td></tr>`}
          </tbody>
        </table>
      </div>`)}
    <button class="secondary" onClick=${load}>🔄 刷新</button>
  </div>`;
}
