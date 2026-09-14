// WorkflowEditor.js —— ★核心：ReactFlow 拖拽 DAG 编辑器。
// 节点类型与后端 NODE_TYPES 严格一致：agent | tool | memory_write | memory_read | approval
import React from 'https://esm.sh/react@18';
import htm from 'https://esm.sh/htm@3';
import ReactFlow, { Background, Controls, MiniMap, useReactFlow, addEdge, ReactFlowProvider } from 'https://esm.sh/reactflow@11.10.4?deps=react@18,react-dom@18';
import { Workflows } from '../api.js';

const h = htm.bind(React.createElement);

const NODE_DEFS = {
  agent: { label: '🤖 Agent', color: '#3b82f6', defaults: { agent_id: '', to_agent: '', content: '' } },
  tool: { label: '🛠 工具', color: '#8b5cf6', defaults: { skill_id: '', owner_agent_id: '', params: {} } },
  memory_write: { label: '✍️ 记忆写入', color: '#10b981', defaults: { owner_agent_id: '', domain: 'global', mem_key: '', content: '' } },
  memory_read: { label: '📖 记忆读取', color: '#14b8a6', defaults: { owner_agent_id: '', domain: 'global', mem_key: '' } },
  approval: { label: '⛔ 人工审批', color: '#f59e0b', defaults: {} },
};

function hasCycle(nodes, edges) {
  const adj = {}; const indeg = {};
  nodes.forEach(n => { adj[n.id] = []; indeg[n.id] = 0; });
  edges.forEach(e => { if (adj[e.source] && adj[e.target]) { adj[e.source].push(e.target); indeg[e.target]++; } });
  const q = nodes.filter(n => indeg[n.id] === 0).map(n => n.id);
  let cnt = 0;
  while (q.length) {
    const cur = q.shift(); cnt++;
    adj[cur].forEach(nxt => { indeg[nxt]--; if (indeg[nxt] === 0) q.push(nxt); });
  }
  return cnt !== nodes.length;
}

function EditorInner({ workflowId, onBack }) {
  const [name, setName] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [status, setStatus] = React.useState('');
  const [nodes, setNodes] = React.useState([]);
  const [edges, setEdges] = React.useState([]);
  const [selectedId, setSelectedId] = React.useState(null);
  const [draft, setDraft] = React.useState('{}');
  const [runResult, setRunResult] = React.useState(null);
  const rf = useReactFlow();

  const selected = nodes.find(n => n.id === selectedId);
  const cycle = hasCycle(nodes, edges);

  async function load() {
    if (!workflowId) return;
    try {
      const r = await Workflows.get(workflowId);
      if (!r.ok) { setStatus('加载失败: ' + JSON.stringify(r)); return; }
      const wf = r.workflow || r;
      setName(wf.name || '');
      setDescription(wf.description || '');
      const def = wf.definition || { nodes: [], edges: [] };
      setNodes((def.nodes || []).map(n => ({
        id: n.id,
        type: 'default',
        position: n.position || { x: Math.random() * 300, y: Math.random() * 200 },
        data: { nodeType: n.type, label: (NODE_DEFS[n.type] || {}).label || n.type, ...(n.data || {}) },
      })));
      setEdges((def.edges || []).map((e, i) => ({ id: 'e_' + i + '_' + Date.now(), source: e.source, target: e.target })));
    } catch (e) { setStatus(e.message); }
  }

  React.useEffect(() => { load(); }, [workflowId]);

  function onConnect(c) { setEdges(es => addEdge(c, es)); }
  function onDragOver(e) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }
  function onDrop(e) {
    e.preventDefault();
    const type = e.dataTransfer.getData('application/reactflow');
    if (!type || !NODE_DEFS[type]) return;
    const pos = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });
    const node = {
      id: 'n_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
      type: 'default',
      position: pos,
      data: { nodeType: type, label: NODE_DEFS[type].label, ...NODE_DEFS[type].defaults },
    };
    setNodes(nds => nds.concat(node));
  }

  function onNodeClick(_, node) {
    setSelectedId(node.id);
    setDraft(JSON.stringify(node.data, null, 2));
  }

  function applyDraft() {
    if (!selected) return;
    try {
      const data = JSON.parse(draft);
      data.nodeType = data.nodeType || selected.data.nodeType;
      setNodes(nds => nds.map(n => n.id === selected.id ? { ...n, data } : n));
      setStatus('节点数据已更新');
    } catch (err) { setStatus('JSON 解析失败: ' + err.message); }
  }

  function buildDefinition() {
    return {
      nodes: nodes.map(n => ({ id: n.id, type: n.data.nodeType || 'agent', position: n.position, data: n.data })),
      edges: edges.map(e => ({ source: e.source, target: e.target })),
    };
  }

  async function save() {
    if (!name.trim()) { setStatus('请先输入工作流名称'); return; }
    if (cycle) { setStatus('❌ 检测到环，后端 Kahn 拓扑排序会拒绝。请删除成环的连线。'); return; }
    setStatus('保存中...');
    try {
      const definition = buildDefinition();
      if (workflowId) {
        const r = await Workflows.update(workflowId, { name: name.trim(), description, definition });
        setStatus('已更新: ' + workflowId + ' ' + JSON.stringify(r));
      } else {
        const r = await Workflows.create({ name: name.trim(), description, definition });
        setStatus('已保存: ' + (r.workflow_id || JSON.stringify(r)));
      }
    } catch (e) { setStatus('保存失败: ' + e.message); }
  }

  async function run() {
    if (!workflowId) { setStatus('请先保存工作流'); return; }
    setRunResult(null);
    setStatus('运行中...');
    try {
      const r = await Workflows.run(workflowId);
      setRunResult(r);
      setStatus('运行结果：' + JSON.stringify(r));
    } catch (e) { setStatus('运行失败: ' + e.message); }
  }

  function delSelected() {
    if (!selected) return;
    setNodes(nds => nds.filter(n => n.id !== selected.id));
    setEdges(es => es.filter(e => e.source !== selected.id && e.target !== selected.id));
    setSelectedId(null);
  }

  return h`
  <div style=${{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 40px)' }}>
    <div class="row" style=${{ marginBottom: 10 }}>
      <button class="secondary" onClick=${onBack}>← 返回</button>
      <input placeholder="工作流名称" value=${name} onInput=${e => setName(e.target.value)} style=${{ minWidth: '220px' }} />
      <input placeholder="描述" value=${description} onInput=${e => setDescription(e.target.value)} style=${{ minWidth: '260px' }} />
      <button onClick=${save}>💾 保存</button>
      <button class="secondary" onClick=${run} disabled=${!workflowId}>▶ 运行</button>
      <button class="danger" onClick=${delSelected} disabled=${!selected}>🗑 删节点</button>
      ${cycle && h`<span class="err">⚠️ 环检测</span>`}
    </div>
    <div style=${{ flex: 1, display: 'flex', minHeight: 0 }}>
      <div style=${{ width: 190, background: '#1f2937', padding: 10, borderRight: '1px solid #374151', overflow: 'auto' }}>
        <h4 class="muted">节点面板（拖到画布）</h4>
        ${Object.entries(NODE_DEFS).map(([key, v]) => h`
          <div key=${key} draggable="true"
            onDragStart=${e => e.dataTransfer.setData('application/reactflow', key)}
            style=${{ padding: 10, marginBottom: 8, background: '#111827', border: '1px solid #374151', borderRadius: 8, cursor: 'grab', borderLeft: '3px solid ' + v.color, userSelect: 'none' }}>${v.label}</div>`)}
      </div>
      <div style=${{ flex: 1, background: '#0b0f19', position: 'relative' }}>
        <${ReactFlow} nodes=${nodes} edges=${edges}
          onConnect=${onConnect} onDrop=${onDrop} onDragOver=${onDragOver}
          onNodeClick=${onNodeClick} fitView>
          <${Background} />
          <${Controls} />
          <${MiniMap} pannable zoomable style=${{ background: '#111827' }} />
        </${ReactFlow}>
      </div>
      <div style=${{ width: 320, background: '#1f2937', borderLeft: '1px solid #374151', padding: 12, overflow: 'auto' }}>
        <h4 class="muted">节点属性（JSON）</h4>
        ${selected
          ? h`<div style=${{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>${selected.data.label} · ${selected.id}</div>
            <textarea value=${draft} onInput=${e => setDraft(e.target.value)} style=${{ width: '100%', height: 280, background: '#111827', color: '#e5e7eb', border: '1px solid #374151', borderRadius: 6, padding: 8, fontSize: 12, fontFamily: 'ui-monospace, monospace', resize: 'vertical' }}></textarea>
            <button style=${{ marginTop: 8 }} onClick=${applyDraft}>更新节点</button>`
          : h`<div style=${{ fontSize: 12, color: '#6b7280' }}>点击节点编辑。

必填提示：
· agent 节点：data.agent_id
· tool 节点：data.skill_id、owner_agent_id
· memory_write/read：owner_agent_id（必填，否则后端 404）、domain、mem_key</div>`}
      </div>
    </div>
    <div style=${{ padding: '8px 12px', background: '#111827', borderTop: '1px solid #374151', fontSize: 12, whiteSpace: 'pre-wrap', maxHeight: 160, overflow: 'auto' }}>${status || '就绪'}</div>
    ${runResult && h`<div style=${{ padding: 10, background: '#111827', fontSize: 12, whiteSpace: 'pre-wrap' }}><pre class="json">${JSON.stringify(runResult, null, 2)}</pre></div>`}
  </div>`;
}

export default function WorkflowEditor(props) {
  return h`<${ReactFlowProvider}><${EditorInner} ...${props} /></${ReactFlowProvider}>`;
}
