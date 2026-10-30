/**
 * AI 数智化后 目标流程图（To-Be）· 知行职业学院实习反馈
 * 每个 AI 能力节点均标注其解决的 As-Is 断点（education-fNNN）。
 */
const W = 1960;
const H = 1290;

const LANE_X = 176;
const lanes = [
  { y: 148, h: 196, name: '企业侧', sub: '企业实习导师 · 5 家企业' },
  { y: 344, h: 236, name: 'AI 能力层', sub: '仅整理与起草，不判定、不打分', ai: true },
  { y: 580, h: 200, name: '教师侧 / 平台服务', sub: '实习指导教师 · 每人 30 人｜批次映射与看板由平台承担' },
  { y: 780, h: 236, name: '教务侧', sub: '教务管理员 · 复核闸门' },
  { y: 1016, h: 174, name: '专业组 / 课程侧', sub: '教学质量负责人 · 专业组' },
];

// type: start|end|step|ai|decision|gate|pain
const nodes = [
  // 企业侧
  { id: 'a1', type: 'start', x: 204, y: 212, w: 150, h: 68, title: '学期实习开始', sub: '600 名学生', fact: 'f00' },
  { id: 'a2', type: 'step', x: 396, y: 206, w: 206, h: 80, title: '① 双周轻量提交', sub: '任务例子 + 行为实例\n替代长问卷', fact: 'f50' },
  { id: 'a3', type: 'step', x: 642, y: 206, w: 206, h: 80, title: '② 企业评分', sub: '口径按校准版本登记', fact: 'f51 · f24' },

  // AI 能力层
  { id: 'b1', type: 'ai', x: 396, y: 386, w: 206, h: 92, title: '③ 评语结构化抽取', sub: '岗位任务·场景·行为实例\n缺项当场标红回填', fact: 'f10 · f41' },
  { id: 'd1', type: 'decision', x: 652, y: 384, w: 186, h: 96, title: '要素齐备？', sub: '任务+实例+版本', fact: 'f10 · f41', fs: 12 },
  { id: 'b2', type: 'ai', x: 884, y: 388, w: 216, h: 88, title: '④ 多源自动收拢', sub: '微信/Excel/邮件归并\n附原文与版本', fact: 'f12 · f15' },
  { id: 'b3', type: 'ai', x: 1140, y: 388, w: 216, h: 88, title: '⑤ 建议起草', sub: '事实 → 建议连原记录\n不做判定', fact: 'f15 · f52' },

  // 教师侧
  { id: 'p0', type: 'pain', x: 652, y: 498, w: 186, h: 52, title: '退回补字段', sub: '不让空值进流程', fact: 'f31', fs: 11 },
  { id: 'c1', type: 'step', x: 396, y: 606, w: 206, h: 88, title: '⑥ 教师确认与修订', sub: '只审异常与判断类\n工时下降', fact: 'f15 · f12' },
  { id: 'd2', type: 'gate', x: 652, y: 598, w: 190, h: 104, title: '异常／争议？', sub: '换岗·无实例·口径', fact: 'f44', fs: 12 },
  { id: 'c2', type: 'step', x: 884, y: 606, w: 216, h: 88, title: '⑦ 异常标记提报', sub: '原记录链接·疑点类型\n·提报人', fact: 'f14', fs: 11 },

  // 教务侧
  { id: 'd3', type: 'gate', x: 884, y: 826, w: 216, h: 104, title: '⑧ 教务核对闸门', sub: '未确认不覆盖原记录', fact: 'f15', fs: 12 },
  { id: 'd4', type: 'gate', x: 1140, y: 826, w: 216, h: 104, title: '⑨ 口径争议？', sub: '记录使用版本', fact: 'f24', fs: 12 },
  { id: 'e1', type: 'step', x: 1396, y: 830, w: 216, h: 96, title: '⑩ 教学质量负责人\n裁定', sub: '人审·不可自动', fact: 'f24 · f44', fs: 11 },
  { id: 'e2', type: 'step', x: 1396, y: 606, w: 216, h: 96, title: '⑪ 批次／导师\n自动映射', sub: '三平台 ID 对齐\n换岗即刷新', fact: 'f30 · f11', fs: 11 },
  { id: 'e3', type: 'step', x: 1640, y: 606, w: 216, h: 96, title: '⑫ 汇总与完整率\n看板', sub: '分母口径固定\n目标 85%', fact: 'f00 · f53', fs: 11 },
  { id: 'e4', type: 'pain', x: 1640, y: 720, w: 216, h: 56, title: '接口失败：只读快照', sub: '按业务编号去重补齐', fact: 'f35', fs: 10 },

  // 专业组 / 课程侧
  { id: 'f1', type: 'step', x: 1640, y: 1062, w: 216, h: 92, title: '⑬ 专业组评审', sub: '30 条中 ≥24 条\n对得上课程才签字', fact: 'f42', fs: 11 },
  { id: 'd5', type: 'gate', x: 1396, y: 1058, w: 216, h: 100, title: '⑭ 结论落到课程？', sub: '任务→能力点→动作', fact: 'f01', fs: 12 },
  { id: 'f2', type: 'step', x: 1140, y: 1062, w: 216, h: 92, title: '⑮ 课程动作下发', sub: '责任主体明确\n进培养方案走审批', fact: 'f22 · f23', fs: 10 },
  { id: 'f3', type: 'step', x: 884, y: 1062, w: 216, h: 92, title: '⑯ 每周复盘', sub: '误判与未解决问题\n定改进负责人', fact: 'f55', fs: 11 },
  { id: 'f4', type: 'end', x: 204, y: 1062, w: 150, h: 92, title: '规则更新', sub: '复测后生效', fact: 'f55', fs: 11 },
  { id: 'f5', type: 'step', x: 396, y: 1062, w: 206, h: 92, title: '⑰ 效果回看', sub: '完整率 + 可执行率', fact: 'f55', fs: 11 },
];

const nById = id => nodes.find(n => n.id === id);

function shape(n) {
  const { x, y, w, h } = n; const cx = x + w / 2, cy = y + h / 2;
  if (n.type === 'decision') return `<polygon points="${cx},${y} ${x + w},${cy} ${cx},${y + h} ${x},${cy}" class="nd-d"/>`;
  if (n.type === 'gate') return `<path d="M${x + 14},${y} H${x + w - 14} L${x + w},${cy} L${x + w - 14},${y + h} H${x + 14} L${x},${cy} Z" class="nd-g"/>`;
  if (n.type === 'start' || n.type === 'end') return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${h / 2}" class="nd-${n.type}"/>`;
  if (n.type === 'ai') return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" class="nd-ai"/><rect x="${x}" y="${y}" width="5" height="${h}" rx="2.5" class="ai-bar"/>`;
  if (n.type === 'pain') return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="6" class="nd-pain"/>`;
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" class="nd-s"/>`;
}

function textBlock(n) {
  const cx = n.x + n.w / 2, fs = n.fs || 13;
  const lines = n.title.split('\n'), subLines = (n.sub || '').split('\n');
  const dark = n.type === 'start' || n.type === 'end';
  const total = lines.length * (fs + 4) + (subLines.length ? 4 + subLines.length * 12 : 0);
  let ty = n.y + n.h / 2 - total / 2 + fs + (n.type === 'decision' ? 1 : 0);
  let out = '';
  for (const l of lines) { out += `<text x="${cx}" y="${ty}" class="tx-t${dark ? '-d' : ''}" font-size="${fs}" style="text-anchor:middle">${l}</text>`; ty += fs + 4; }
  if (subLines.length) { ty += 2; for (const l of subLines) { out += `<text x="${cx}" y="${ty}" class="${dark ? 'tx-sd' : 'tx-s'}" style="text-anchor:middle">${l}</text>`; ty += 12; } }
  return out;
}

function factChip(n) {
  if (!n.fact) return '';
  const label = n.fact;
  const cx = n.x + n.w - 8, cy = n.y + 11;
  const w = 14 + label.length * 5.6;
  return `<g><rect x="${cx - w}" y="${cy - 9.5}" width="${w}" height="15" rx="7.5" class="chip"/>` +
    `<text x="${cx - w / 2}" y="${cy + 2}" class="chip-t" style="text-anchor:middle">${label}</text></g>`;
}

const edges = [
  { a: 'a1', b: 'a2' }, { a: 'a2', b: 'a3' },
  { a: 'a3', b: 'b1', dir: 'down' },
  { a: 'b1', b: 'd1' },
  { a: 'd1', b: 'p0', label: '否', dir: 'down', style: 'warn' },
  { a: 'p0', b: 'a2', dir: 'loopback' },
  { a: 'd1', b: 'b2', label: '是' },
  { a: 'b2', b: 'b3' },
  { a: 'b3', b: 'c1', dir: 'down' },
  { a: 'c1', b: 'd2' },
  { a: 'd2', b: 'c2', label: '是', dir: 'up' },
  { a: 'c2', b: 'd3', dir: 'down' },
  { a: 'd2', b: 'd3', label: '否', dir: 'down' },
  { a: 'd3', b: 'd4' },
  { a: 'd4', b: 'e1', label: '是' },
  { a: 'e1', b: 'e2', dir: 'up' },
  { a: 'd3', b: 'e2', dir: 'up' },
  { a: 'e2', b: 'e3' },
  { a: 'e3', b: 'e4', dir: 'down', dashed: true, style: 'warn' },
  { a: 'e3', b: 'f1', dir: 'down' },
  { a: 'f1', b: 'd5' },
  { a: 'd5', b: 'f2', label: '是' },
  { a: 'f2', b: 'f3' },
  { a: 'f3', b: 'f5' },
  { a: 'f5', b: 'f4' },
  { a: 'd5', b: 'f1', label: '否→退回补', dir: 'self' },
];

function route(a, b, mode) {
  const ax = a.x + a.w / 2, ay = a.y + a.h / 2, aR = a.x + a.w, aL = a.x, aB = a.y + a.h, aT = a.y;
  const bx = b.x + b.w / 2, by = b.y + b.h / 2, bL = b.x, bT = b.y, bB = b.y + b.h, bR = b.x + b.w;
  if (mode === 'down') { const my = (aB + bT) / 2; return `M${ax},${aB} L${ax},${my} L${bx},${my} L${bx},${bT}`; }
  if (mode === 'up') { const my = (aT + bB) / 2; return `M${ax},${aT} L${ax},${my} L${bx},${my} L${bx},${bB}`; }
  if (mode === 'loopback') { return `M${a.x},${a.y + a.h / 2} L${a.x - 34},${a.y + a.h / 2} L${a.x - 34},${b.y + b.h / 2} L${b.x + b.w},${b.y + b.h / 2}`; }
  if (mode === 'self') { const rx = aR + 22; return `M${aR - 30},${aT} L${aR - 30},${aT - 18} L${rx},${aT - 18} L${rx},${aT + 16} L${aR - 2},${aT + 16}`; }
  if (b.x > a.x) return `M${aR},${ay} L${bL},${by}`;
  return `M${aL},${ay} L${bR},${by}`;
}

const edgeHtml = edges.map(e => {
  const a = nById(e.a), b = nById(e.b), d = route(a, b, e.dir || 'h');
  const cls = ['eg']; if (e.dashed) cls.push('eg-dash');
  if (e.style === 'warn') cls.push('eg-warn');
  if (e.a === 'd2' && e.b !== 'c2') cls.push('eg-main');
  let lb = '';
  if (e.label) {
    const ax = a.x + a.w / 2, ay = a.y + a.h / 2, bx = b.x + b.w / 2, by = b.y + b.h / 2;
    let lx, ly;
    if (e.dir === 'down') { lx = ax + 16; ly = (a.y + a.h + b.y) / 2 + 4; }
    else if (e.dir === 'up') { lx = ax + 16; ly = (a.y + b.y + b.h) / 2 - 2; }
    else { lx = (ax + bx) / 2; ly = (ay + by) / 2 - 7; }
    lb = `<rect x="${lx - 9}" y="${ly - 11}" width="18" height="15" rx="4" class="lb-bg"/><text x="${lx}" y="${ly}" class="lb">${e.label}</text>`;
  }
  const mk = e.style === 'warn' ? 'arwW' : 'arw';
  return `<g><path d="${d}" class="${cls.join(' ')}" marker-end="url(#${mk})"/>${lb}</g>`;
}).join('\n');

const laneHtml = lanes.map(l => `<g><rect x="${LANE_X}" y="${l.y}" width="${W - LANE_X - 36}" height="${l.h}" class="${l.ai ? 'lane lane-ai' : 'lane'}"/>` +
  `<text x="${LANE_X + 18}" y="${l.y + 32}" class="lane-t${l.ai ? '-ai' : ''}">${l.name}</text>` +
  `<text x="${LANE_X + 18}" y="${l.y + 50}" class="lane-s">${l.sub}</text></g>`).join('\n');

const nodeHtml = nodes.map(n => `<g>${shape(n)}${textBlock(n)}${factChip(n)}</g>`).join('\n');

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="'Microsoft YaHei','PingFang SC','Noto Sans SC',sans-serif">
<defs>
  <marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#3F4B5C"/></marker>
  <marker id="arwW" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#B4690E"/></marker>
  <style>
    .bg{fill:#FFFFFF}
    .lane{fill:#F7F9FC;stroke:#DDE3EC;stroke-width:1}
    .lane-ai{fill:#F1F7F4;stroke:#C9E2D6;stroke-width:1.2}
    .lane-t{font-size:14px;font-weight:700;fill:#1A237E}
    .lane-t-ai{font-size:14px;font-weight:700;fill:#15604A}
    .lane-s{font-size:11.5px;fill:#4E5A6B}
    .nd-s{fill:#FFFFFF;stroke:#1565C0;stroke-width:1.3}
    .nd-ai{fill:#EEF7F2;stroke:#1E8A63;stroke-width:1.5}
    .ai-bar{fill:#1E8A63}
    .nd-d{fill:#FFF8E8;stroke:#B4690E;stroke-width:1.4}
    .nd-g{fill:#FDECEA;stroke:#B3271E;stroke-width:1.6}
    .nd-start{fill:#1565C0;stroke:#1565C0}
    .nd-end{fill:#1A237E;stroke:#1A237E}
    .nd-pain{fill:#FFF6E5;stroke:#B4690E;stroke-width:1;stroke-dasharray:4 3}
    .tx-t{fill:#1B2430;font-weight:600}
    .tx-t-d{fill:#FFFFFF;font-weight:700}
    .tx-s{font-size:11px;fill:#4E5A6B}
    .tx-sd{font-size:10.5px;fill:#E3EEFB}
    .chip{fill:#EDF2FA;stroke:#C9D8EC;stroke-width:0.8}
    .chip-t{font-size:9px;fill:#2C5A96;font-weight:700}
    .eg{fill:none;stroke:#3F4B5C;stroke-width:1.4}
    .eg-main{stroke-width:1.7}
    .eg-dash{stroke-dasharray:5 4}
    .eg-warn{stroke:#B4690E}
    .lb{font-size:10px;fill:#3F4B5C;text-anchor:middle;font-weight:700}
    .lb-bg{fill:#FFFFFF}
    .ttl{font-size:27px;font-weight:700;fill:#1A237E}
    .stl{font-size:13px;fill:#4E5A6B}
    .lg{font-size:11.5px;fill:#3F4B5C}
    .hn{font-size:12.5px;font-weight:700;fill:#1A237E}
  </style>
</defs>
<rect width="${W}" height="${H}" class="bg"/>
${laneHtml}
${edgeHtml}
${nodeHtml}

<text x="40" y="50" class="ttl">知行职业学院 · AI 数智化后实习反馈流程（To-Be）</text>
<text x="40" y="76" class="stl">目标链路：双周结构化提交 → AI 收拢与起草 → 教师确认 → 教务核对闸门 → 专业组落课 → 每周复盘更新规则　|　共 17 步，5 道人工闸门全部保留</text>
<text x="40" y="98" class="stl">绿色节点 = AI 承担（只做抽取、归并与起草，不判定、不打分）　·　红色六边形 = 人工闸门　·　依据 discovery-report.json（education-fNNN）</text>

<g transform="translate(40, 112)">
  <rect x="0" y="0" width="26" height="16" rx="4" fill="#EEF7F2" stroke="#1E8A63" stroke-width="1.5"/><rect x="0" y="0" width="4" height="16" rx="2" fill="#1E8A63"/>
  <text x="34" y="13" class="lg">AI 能力</text>
  <path d="M104,8 H152 L164,16 L152,24 H104 L92,16 Z" fill="#FDECEA" stroke="#B3271E" stroke-width="1.6" transform="translate(-2,-8)"/>
  <text x="172" y="13" class="lg">人工闸门</text>
  <rect x="258" y="0" width="26" height="16" rx="4" fill="#FFF6E5" stroke="#B4690E" stroke-dasharray="4 3"/>
  <text x="292" y="13" class="lg">规则/兜底</text>
</g>

<g transform="translate(${W - 500}, 148)">
  <rect x="0" y="0" width="462" height="96" rx="8" fill="#FFFFFF" stroke="#DDE3EC"/>
  <text x="14" y="22" class="hn">解决的现状断点</text>
  <text x="14" y="42" class="lg" style="font-size:11px">① 评语无行为实例（f10）→ ③ 抽取时强制补齐</text>
  <text x="14" y="60" class="lg" style="font-size:11px">② 整理 10h/月（f12）→ ④ 多源自动归并</text>
  <text x="14" y="78" class="lg" style="font-size:11px">③ 换岗旧导师（f11）→ ⑪ 换岗即刷新映射</text>
  <text x="240" y="42" class="lg" style="font-size:11px">④ 建议落不到课程（f01）→ ⑭ 落课判定</text>
  <text x="240" y="60" class="lg" style="font-size:11px">⑤ 完整率 54%（f00）→ ① 双周轻量提交</text>
  <text x="240" y="78" class="lg" style="font-size:11px">⑥ 群聊补录（f14）→ ⑦ 结构化异常位</text>
</g>
</svg>`;

require('fs').writeFileSync('D:/education_expense/output/flowchart/ai-tobe-flow.svg', svg, 'utf8');
console.log('written', svg.length);
