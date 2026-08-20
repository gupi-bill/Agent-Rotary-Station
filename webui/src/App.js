// App.js —— 多页面控制台壳：侧边栏导航 + 页面切换。
// 零构建：htm 模板字符串 + ES module，浏览器原生加载，不引入任何 LLM/向量/构建步骤。
import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import Dashboard from './pages/Dashboard.js';
import Agents from './pages/Agents.js';
import Chat from './pages/Chat.js';
import Memories from './pages/Memories.js';
import Skills from './pages/Skills.js';
import System from './pages/System.js';
import Workflows from './pages/Workflows.js';
import WorkflowEditor from './pages/WorkflowEditor.js';
import ApprovalInbox from './pages/ApprovalInbox.js';

const h = htm.bind(React.createElement);

const NAV = [
  { key: 'dashboard', label: '📊 总览', el: Dashboard },
  { key: 'agents', label: '🤖 Agent 管理', el: Agents },
  { key: 'chat', label: '💬 聊天', el: Chat },
  { key: 'memories', label: '🧠 记忆池', el: Memories },
  { key: 'skills', label: '🛠 技能市场', el: Skills },
  { key: 'workflows', label: '🔀 工作流', el: Workflows },
  { key: 'inbox', label: '📥 审批收件箱', el: ApprovalInbox },
  { key: 'system', label: '🛡 系统面板', el: System },
];

export default function App() {
  const [page, setPage] = React.useState('dashboard');
  const [editingId, setEditingId] = React.useState(null); // 非空时进入工作流编辑器

  function nav(key) {
    setEditingId(null);
    setPage(key);
  }

  function openEditor(id) {
    setEditingId(id || null);
    setPage('editor');
  }

  let content;
  if (page === 'editor') {
    content = h`<${WorkflowEditor} workflowId=${editingId} onBack=${() => nav('workflows')} />`;
  } else {
    const item = NAV.find(n => n.key === page) || NAV[0];
    const Page = item.el;
    content = h`<${Page} onOpenEditor=${openEditor} />`;
  }

  return h`
  <div className="app">
    <aside className="sidebar">
      <div className="brand">🔄 轮转工作站</div>
      <nav className="nav">
        ${NAV.map(n => h`
          <button key=${n.key}
            className=${'nav-item' + (page === n.key ? ' active' : '')}
            onClick=${() => nav(n.key)}>${n.label}</button>`)}
      </nav>
      <div className="muted" style=${{ padding: '10px 12px', borderTop: '1px solid var(--border)' }}>
        v0.2 · 零大模型底座
      </div>
    </aside>
    <main className="content">${content}</main>
  </div>`;
}
