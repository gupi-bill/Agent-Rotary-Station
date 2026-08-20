import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import { Agents, Workflows, Memories, Tools, System } from '../api.js';
const h = htm.bind(React.createElement);

export default function Dashboard() {
  const [stats, setStats] = React.useState(null);
  const [err, setErr] = React.useState('');

  async function load() {
    setErr('');
    try {
      const [agents, workflows, memPending, toolPending, health] = await Promise.all([
        Agents.list(), Workflows.list(), Memories.pending(), Tools.requestsPending(), System.health(),
      ]);
      setStats({
        agents: agents.agents || [],
        workflows: workflows.workflows || [],
        memPending: memPending.pending || memPending.requests || [],
        toolPending: toolPending.pending || [],
        health: health,
      });
    } catch (e) { setErr(e.message); }
  }

  React.useEffect(() => { load(); }, []);

  const online = stats ? stats.agents.filter(a => a.status === 'online').length : 0;
  const manager = stats ? stats.agents.find(a => a.role === 'manager') : null;
  const pendingCount = stats ? (stats.memPending.length + stats.toolPending.length) : 0;

  return h`
  <div>
    <h2 class="page-title">📊 总览</h2>
    ${err && h`<div class="toast">${err}</div>`}
    <div class="grid">
      <div class="stat"><div class="num">${stats ? stats.agents.length : '-'}</div><div class="lbl">Agent 总数</div></div>
      <div class="stat"><div class="num">${online}</div><div class="lbl">在线 Agent</div></div>
      <div class="stat"><div class="num">${stats ? stats.workflows.length : '-'}</div><div class="lbl">工作流</div></div>
      <div class="stat"><div class="num">${pendingCount}</div><div class="lbl">待审批</div></div>
    </div>
    <div class="card">
      <h3>🧭 管理岗</h3>
      <div>${manager ? h`<span class="chip">${manager.name} (${manager.agent_id})</span>` : h`<span class="dim">暂无管理岗</span>`}</div>
    </div>
    <div class="card">
      <h3>🛑 紧急刹车</h3>
      <div class=${stats && stats.health && stats.health.emergency_block ? 'err' : 'ok'}>
        ${stats && stats.health && stats.health.emergency_block ? '已启用（底座最高拦截生效）' : '未启用'}
      </div>
    </div>
    <button class="secondary" onClick=${load}>🔄 刷新</button>
  </div>`;
}
