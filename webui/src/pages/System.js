import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import { System as SystemApi } from '../api.js';
const h = htm.bind(React.createElement);

export default function System() {
  const [health, setHealth] = React.useState(null);
  const [block, setBlock] = React.useState(false);
  const [logs, setLogs] = React.useState([]);
  const [msg, setMsg] = React.useState('');

  async function load() {
    try {
      const [hres, bres, lres] = await Promise.all([
        SystemApi.health(), SystemApi.emergencyBlock(), SystemApi.auditLogs(100),
      ]);
      setHealth(hres);
      setBlock(bres.emergency_block);
      setLogs(lres.logs || []);
    } catch (e) { setMsg(e.message); }
  }
  React.useEffect(() => { load(); }, []);

  async function toggle() {
    try {
      const r = await SystemApi.toggleBlock(!block);
      setBlock(r.emergency_block);
      setMsg('紧急刹车已' + (r.emergency_block ? '启用' : '关闭'));
      load();
    } catch (e) { setMsg(e.message); }
  }

  async function manual(which) {
    try {
      if (which === 'heartbeat') { await SystemApi.heartbeatCheck(); }
      else if (which === 'queue') { await SystemApi.toolQueueProcess(); }
      setMsg('已触发');
    } catch (e) { setMsg(e.message); }
  }

  return h`
  <div>
    <h2 class="page-title">⚙️ 系统面板</h2>
    ${msg && h`<div class="toast">${msg}</div>`}
    <div class="card">
      <h3>健康状态</h3>
      <pre class="json">${JSON.stringify(health || {}, null, 2)}</pre>
    </div>
    <div class="card">
      <h3>🛑 紧急刹车</h3>
      <div class="row">
        <span class=${block ? 'err' : 'ok'}>${block ? '已启用' : '未启用'}</span>
        <button class=${block ? 'secondary' : 'danger'} onClick=${toggle}>${block ? '关闭刹车' : '启动刹车'}</button>
      </div>
    </div>
    <div class="card">
      <h3>手动触发</h3>
      <div class="row">
        <button class="secondary" onClick=${() => manual('heartbeat')}>心跳超时检查</button>
        <button class="secondary" onClick=${() => manual('queue')}>补发离线工具队列</button>
      </div>
    </div>
    <div class="card">
      <h3>审计日志（最近 100 条）</h3>
      <table class="table">
        <thead><tr><th>时间</th><th>Actor</th><th>动作</th><th>目标</th><th>详情</th></tr></thead>
        <tbody>
          ${logs.map(l => h`<tr key=${l.id}>
            <td class="muted">${l.created_at || ''}</td>
            <td>${l.actor}</td>
            <td>${l.action}</td>
            <td>${l.target || ''}</td>
            <td class="muted">${JSON.stringify(l.detail)}</td>
          </tr>`)}
        </tbody>
      </table>
    </div>
    <button class="secondary" onClick=${load}>🔄 刷新</button>
  </div>`;
}
