// ApprovalInbox.js —— 统一审批收件箱：记忆审批 + 工具审批 + 工作流挂起。
import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import { Memories, Tools, Workflows } from '../api.js';
import { store } from '../store.js';
const h = htm.bind(React.createElement);

export default function ApprovalInbox() {
  const [mem, setMem] = React.useState([]);
  const [tool, setTool] = React.useState([]);
  const [wf, setWf] = React.useState([]);
  const [msg, setMsg] = React.useState('');

  async function load() {
    setMsg('');
    try {
      const [m, t, w] = await Promise.all([
        Memories.pending(),
        Tools.requestsPending(),
        Workflows.list(),
      ]);
      setMem(m.pending || m.requests || []);
      setTool(t.pending || t.requests || []);
      // 找出所有 awaiting_approval 的 run（拉每个工作流的 runs）
      const wfs = w.workflows || [];
      const allRuns = [];
      for (const wfItem of wfs) {
        try {
          const r = await Workflows.runs(wfItem.workflow_id);
          const runs = r.runs || r.run_list || [];
          runs.filter(x => x.status === 'awaiting_approval').forEach(x => {
            allRuns.push({ ...x, workflow_id: wfItem.workflow_id, workflow_name: wfItem.name });
          });
        } catch { /* 忽略单个失败 */ }
      }
      setWf(allRuns);
    } catch (e) { setMsg(e.message); }
  }

  React.useEffect(() => {
    load();
    const un = store.subscribe(load);
    return un;
  }, []);

  async function memDecide(id, approve) {
    setMsg('');
    try {
      await Memories.decide({ manager_id: 'human', request_id: id, approve });
      setMsg('已' + (approve ? '批准' : '拒绝') + '记忆审批 ' + id);
      await load();
    } catch (e) { setMsg(e.message); }
  }

  async function toolDecide(id, approve) {
    setMsg('');
    try {
      await Tools.decide({ manager_id: 'human', request_id: id, approve });
      setMsg('已' + (approve ? '批准' : '拒绝') + '工具审批 ' + id);
      await load();
    } catch (e) { setMsg(e.message); }
  }

  async function wfApprove(runId) {
    setMsg('');
    try { await Workflows.approveRun(runId); setMsg('已批准工作流 run ' + runId); await load(); }
    catch (e) { setMsg(e.message); }
  }
  async function wfDeny(runId) {
    setMsg('');
    try { await Workflows.denyRun(runId); setMsg('已拒绝工作流 run ' + runId); await load(); }
    catch (e) { setMsg(e.message); }
  }

  return h`
  <div>
    <h2 class="page-title">📥 审批收件箱</h2>
    ${msg && h`<div class="toast">${msg}</div>`}
    <div class="card">
      <h3>记忆审批（${mem.length}）</h3>
      <table class="table">
        <thead><tr><th>request_id</th><th>agent_id</th><th>domain</th><th>mem_key</th><th>操作</th></tr></thead>
        <tbody>
          ${mem.map(r => h`<tr key=${r.request_id}>
            <td>${r.request_id}</td>
            <td>${r.agent_id || r.requester || '-'}</td>
            <td>${r.domain || '-'}</td>
            <td>${r.mem_key || '-'}</td>
            <td class="row">
              <button class="ghost" onClick=${() => memDecide(r.request_id, true)}>✅</button>
              <button class="ghost danger" onClick=${() => memDecide(r.request_id, false)}>❌</button>
            </td>
          </tr>`)}
          ${mem.length === 0 && h`<tr><td colspan=5 class="dim">无待审批</td></tr>`}
        </tbody>
      </table>
    </div>
    <div class="card">
      <h3>工具审批（${tool.length}）</h3>
      <table class="table">
        <thead><tr><th>request_id</th><th>skill_id</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          ${tool.map(r => h`<tr key=${r.request_id || r.id}>
            <td>${r.request_id || r.id}</td>
            <td>${r.skill_id || '-'}</td>
            <td>${r.status || 'pending'}</td>
            <td class="row">
              <button class="ghost" onClick=${() => toolDecide(r.request_id || r.id, true)}>✅</button>
              <button class="ghost danger" onClick=${() => toolDecide(r.request_id || r.id, false)}>❌</button>
            </td>
          </tr>`)}
          ${tool.length === 0 && h`<tr><td colspan=4 class="dim">无待审批</td></tr>`}
        </tbody>
      </table>
    </div>
    <div class="card">
      <h3>工作流挂起（${wf.length}）</h3>
      <table class="table">
        <thead><tr><th>run_id</th><th>工作流</th><th>当前节点</th><th>操作</th></tr></thead>
        <tbody>
          ${wf.map(r => h`<tr key=${r.run_id}>
            <td>${r.run_id}</td>
            <td>${r.workflow_name || r.workflow_id}</td>
            <td>${r.current_node || '-'}</td>
            <td class="row">
              <button class="ghost" onClick=${() => wfApprove(r.run_id)}>✅ 批准</button>
              <button class="ghost danger" onClick=${() => wfDeny(r.run_id)}>❌ 拒绝</button>
            </td>
          </tr>`)}
          ${wf.length === 0 && h`<tr><td colspan=4 class="dim">无挂起</td></tr>`}
        </tbody>
      </table>
    </div>
    <button class="secondary" onClick=${load}>🔄 刷新</button>
  </div>`;
}
