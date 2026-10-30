/**
 * 现状流程图（as-is）· 知行职业学院实习反馈
 * 依据 discovery-report.json 访谈事实（education-fNNN）绘制，不含推测环节。
 */
const NOT_VERIFIED = '#8A8F98';
const INK = '#1A237E';

const W = 1860;
const H = 1140;

// 泳道
const lanes = [
  { y: 150, h: 200, name: '企业侧', sub: '企业实习导师 · 5 家企业' },
  { y: 350, h: 210, name: '教师侧', sub: '实习指导教师 · 每人 30 人' },
  { y: 560, h: 250, name: '教务侧', sub: '教务管理员' },
  { y: 810, h: 180, name: '专业组', sub: '教学质量负责人 · 专业组评审' },
  { y: 990, h: 120, name: '课程侧', sub: '课程与培养方案', gap: true },
];
const LANE_X = 170;

// 节点：type = start|step|decision|end|pain
const nodes = [
  // 企业侧
  { id: 's1', type: 'start', x: 200, y: 210, w: 150, h: 66, title: '学期实习开始', sub: '600 名学生 / 学期', fact: 'f00' },
  { id: 's2', type: 'step', x: 400, y: 204, w: 200, h: 78, title: '① 企业评分与评语', sub: '企业导师按自身口径打分', fact: 'f01 · f51' },
  { id: 'd1', type: 'decision', x: 660, y: 196, w: 200, h: 94, title: '评语含岗位任务', sub: '与行为实例？', fact: 'f10 · f41' },
  { id: 'x1', type: 'pain', x: 660, y: 300, w: 200, h: 54, title: '只写"沟通能力不足"', sub: '不知发生在哪个任务', fact: 'f10' },

  // 教师侧
  { id: 's3', type: 'step', x: 400, y: 400, w: 200, h: 90, title: '② 教师回访与复核', sub: '追问任务／场景／事例\n每人 30 人', fact: 'f01 · f12' },
  { id: 's4', type: 'step', x: 660, y: 396, w: 200, h: 98, title: '③ 反馈收拢整理', sub: '微信 · Excel · 邮件\n手动搬运归类', fact: 'f12' },
  { id: 'p1', type: 'pain', x: 660, y: 512, w: 200, h: 50, title: '≈10 小时 / 月 / 人', sub: '不产出教学判断', fact: 'f12' },
  { id: 's5', type: 'step', x: 920, y: 404, w: 200, h: 84, title: '④ 提出改进建议', sub: '面向学生与课程', fact: 'f01' },

  // 教务侧
  { id: 'd2', type: 'decision', x: 920, y: 600, w: 200, h: 96, title: '提交前核对：\n换岗／无实例／口径不一致？', fact: 'f15 · f44', fs: 11 },
  { id: 'x2', type: 'pain', x: 920, y: 736, w: 200, h: 54, title: '群聊／个人表补说明', sub: '再回系统补录，原因不随单流转', fact: 'f14' },
  { id: 's6', type: 'step', x: 1180, y: 600, w: 200, h: 96, title: '⑤ 教务管理员核对', sub: '记录版本，交教学质量负责人确认\n未确认不覆盖原记录', fact: 'f15 · f24', fs: 11 },
  { id: 's7', type: 'step', x: 1180, y: 400, w: 200, h: 84, title: '⑥ 教务汇总', sub: '汇总各专业反馈与建议', fact: 'f01' },
  { id: 'p2', type: 'pain', x: 1440, y: 404, w: 200, h: 76, title: '完整率 54%（目标 85%）', sub: '样本基础不完整', fact: 'f00' },
  { id: 's8', type: 'step', x: 1440, y: 604, w: 200, h: 84, title: '⑦ 批次／导师映射\n抽检', sub: '多平台 ID 不一致', fact: 'f30 · f33', fs: 11 },
  { id: 'p3', type: 'pain', x: 1440, y: 720, w: 200, h: 50, title: '换岗后仍关联旧导师', sub: '反馈发给错误的人', fact: 'f11' },

  // 专业组
  { id: 's9', type: 'step', x: 1440, y: 860, w: 220, h: 86, title: '⑧ 专业组评审', sub: '专业组层面结论', fact: 'f01' },
  { id: 'd3', type: 'decision', x: 1180, y: 860, w: 200, h: 84, title: '结论落到\n具体课程？', fact: 'f01' },
  { id: 's10', type: 'step', x: 920, y: 862, w: 200, h: 80, title: '⑨ 课程层面\n转换与排期', sub: '责任归属未定（教师 or 教务）', fact: 'f20 · f23', fs: 11 },
  { id: 'x3', type: 'pain', x: 1440, y: 986, w: 220, h: 44, title: '停在专业组，进不了课程', sub: '每学期重复', fact: 'f01', fs: 10 },
  { id: 's11', type: 'step', x: 660, y: 862, w: 200, h: 80, title: '⑩ 课程动作执行', sub: '按转换结果调整教学', fact: 'f22', fs: 11 },
  { id: 's12', type: 'step', x: 400, y: 862, w: 200, h: 80, title: '⑪ 效果回看', sub: '下一轮企业反馈比对', fact: 'f55', fs: 11 },
  { id: 'e1', type: 'end', x: 200, y: 862, w: 150, h: 80, title: '下一学期实习', sub: '链路重新开始', fact: 'f01', fs: 11 },
];

function nodeById(id) { return nodes.find(n => n.id === id); }

function shape(n) {
  const { x, y, w, h } = n;
  const cx = x + w / 2, cy = y + h / 2;
  if (n.type === 'decision') {
    return `<polygon points="${cx},${y} ${x + w},${cy} ${cx},${y + h} ${x},${cy}" class="nd-d"/>`;
  }
  if (n.type === 'start' || n.type === 'end') {
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${h / 2}" class="nd-${n.type}"/>`;
  }
  if (n.type === 'pain') {
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="6" class="nd-pain"/>`;
  }
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" class="nd-s"/>`;
}

function textBlock(n) {
  const cx = n.x + n.w / 2;
  const lines = n.title.split('\n');
  const fs = n.fs || 13;
  const subLines = (n.sub || '').split('\n');
  const gapTop = n.type === 'decision' ? 2 : 0;
  const total = lines.length * (fs + 4) + (subLines.length ? 4 + subLines.length * 12 : 0);
  let ty = n.y + n.h / 2 - total / 2 + fs + gapTop;
  let out = '';
  for (const l of lines) {
    out += `<text x="${cx}" y="${ty}" class="tx-t" font-size="${fs}" style="text-anchor:middle">${l}</text>`;
    ty += fs + 4;
  }
  const dark = (n.type === 'start' || n.type === 'end');
  if (subLines.length) {
    ty += 2;
    for (const l of subLines) {
      out += `<text x="${cx}" y="${ty}" class="${dark ? 'tx-sd' : 'tx-s'}" style="text-anchor:middle">${l}</text>`;
      ty += 12;
    }
  }
  return out;
}

function factChip(n) {
  if (!n.fact) return '';
  const label = n.fact.split(' · ').map(f => f).join('·');
  const cx = n.x + n.w - 6;
  const cy = n.y + 10;
  const w = 14 + label.length * 5.6;
  return `<g><rect x="${cx - w}" y="${cy - 9}" width="${w}" height="15" rx="7.5" class="chip"/>` +
    `<text x="${cx - w / 2}" y="${cy + 2}" class="chip-t" style="text-anchor:middle">${label}</text></g>`;
}

// 连线：from -> to，orth = 直角走线
const edges = [
  { a: 's1', b: 's2' },
  { a: 's2', b: 'd1' },
  { a: 'd1', b: 'x1', label: '否', dir: 'down' },
  { a: 'd1', b: 's3', label: '是', dir: 'down' },
  { a: 'x1', b: 's3', dashed: true, style: 'pain' },
  { a: 's3', b: 's4' },
  { a: 's4', b: 'p1', dashed: true, dir: 'down', style: 'pain' },
  { a: 's4', b: 's5' },
  { a: 's5', b: 's7', label: '', dir: 'up' },   // 建议上交汇总（走上方）
  { a: 's5', b: 'd2', dir: 'down' },
  { a: 'd2', b: 'x2', label: '有疑点', dir: 'down' },
  { a: 'd2', b: 's6', label: '无疑点' },
  { a: 'x2', b: 's6', dashed: true, dir: 'side' },
  { a: 's6', b: 's7', dir: 'up' },
  { a: 's7', b: 'p2', dashed: true, style: 'pain' },
  { a: 's7', b: 's9', dir: 'right-down' },
  { a: 's8', b: 'p3', dashed: true, dir: 'down', style: 'pain' },
  { a: 's8', b: 's7', dir: 'up' },
  { a: 's9', b: 'd3' },
  { a: 'd3', b: 's10', label: '是', style: 'ok' },
  { a: 'd3', b: 'x3', label: '否', dir: 'down' },
  { a: 's10', b: 's11' },
  { a: 's11', b: 's12' },
  { a: 's12', b: 'e1' },
];

function pathFor(a, b) {
  const ax = a.x + a.w / 2, ay = a.y + a.h / 2;
  const bx = b.x + b.w / 2, by = b.y + b.h / 2;
  const aRight = a.x + a.w, aLeft = a.x, aTop = a.y, aBot = a.y + a.h;
  const bLeft = b.x, bTop = b.y, bBot = b.y + b.h, bRight = b.x + b.w;

  // 同一行：右 -> 左
  if (Math.abs(ay - by) < 30 && b.x > a.x) {
    return `M${aRight},${ay} L${bLeft},${by}`;
  }
  // 同一行：右 -> 左（b 在 a 左侧）
  if (Math.abs(ay - by) < 30 && b.x < a.x) {
    return `M${aLeft},${ay} L${bRight},${by}`;
  }
  // 目标在下方（正下或偏下）
  if (bbox(b) && by > ay + 20) {
    // 水平有重叠 -> 垂直直线
    if (bx >= a.x - 4 && bx <= aRight + 4) {
      return `M${bx},${aBot} L${bx},${bTop}`;
    }
    const midY = aBot + (bTop - aBot) / 2;
    const sx = ax < bx ? aRight : aLeft;
    const ex = ax < bx ? bLeft : bRight;
    if (bTop > midY) {
      return `M${sx},${ay} L${(sx + ex) / 2 + (ax < bx ? 0 : 0)},${ay} L${ex},${ay} L${ex},${by}`;
    }
  }
  return '';
}
function bbox(n) { return n; }

function route(a, b, mode) {
  const ax = a.x + a.w / 2, ay = a.y + a.h / 2;
  const bx = b.x + b.w / 2, by = b.y + b.h / 2;
  const aRight = a.x + a.w, aLeft = a.x, aBot = a.y + a.h, aTop = a.y;
  const bLeft = b.x, bTop = b.y, bBot = b.y + b.h, bRight = b.x + b.w;

  if (mode === 'down') {
    return `M${ax},${aBot} L${ax},${(aBot + bTop) / 2} L${bx},${(aBot + bTop) / 2} L${bx},${bTop}`;
  }
  if (mode === 'up') {
    return `M${ax},${aTop} L${ax},${(aTop + bBot) / 2} L${bx},${(aTop + bBot) / 2} L${bx},${bBot}`;
  }
  if (mode === 'side') {
    const sx = b.x > a.x ? aRight : aLeft;
    const ex = b.x > a.x ? bLeft : bRight;
    const midY = (ay + by) / 2;
    return `M${sx},${ay} L${midY === 0 ? 0 : (sx + ex) / 2},${ay} L${(sx + ex) / 2},${by} L${ex},${by}`;
  }
  if (mode === 'right-down') {
    // 从右侧下沿拐出，绕到目标顶部
    const ex = bLeft - 26;
    return `M${aRight - 40},${aBot} L${aRight - 40},${aBot + 20} L${ex},${aBot + 20} L${ex},${bTop - 24} L${bx},${bTop - 24} L${bx},${bTop}`;
  }
  if (mode === 'corner') {
    const ex = bLeft - 60;
    return `M${aRight},${ay} L${ex},${ay} L${ex},${bTop - 20} L${bx},${bTop - 20} L${bx},${bTop}`;
  }
  // 默认：同行左右
  if (b.x > a.x) return `M${aRight},${ay} L${bLeft},${by}`;
  return `M${aLeft},${ay} L${bRight},${by}`;
}

const edgeHtml = edges.map(e => {
  const a = nodeById(e.a), b = nodeById(e.b);
  const d = route(a, b, e.dir || (b.x > a.x ? 'h' : 'h'));
  const cls = ['eg'];
  if (e.dashed) cls.push('eg-dash');
  if (e.style === 'pain') cls.push('eg-pain');
  if (e.style === 'ok') cls.push('eg-ok');
  let labelHtml = '';
  if (e.label) {
    // 标签取路径中点附近
    const ax = a.x + a.w / 2, ay = a.y + a.h / 2;
    const bx = b.x + b.w / 2, by = b.y + b.h / 2;
    let lx, ly;
    if (e.dir === 'down') { lx = ax + 14; ly = (a.y + a.h + b.y) / 2 + 4; }
    else if (e.dir === 'up') { lx = ax + 14; ly = (a.y + b.y + b.h) / 2 - 2; }
    else { lx = (ax + bx) / 2; ly = (ay + by) / 2 - 7; }
    labelHtml = `<rect x="${lx - 9}" y="${ly - 11}" width="18" height="15" rx="4" class="lb-bg"/><text x="${lx}" y="${ly}" class="lb">${e.label}</text>`;
  }
  return `<g>${`<path d="${d}" class="${cls.join(' ')}" marker-end="url(#${e.style === 'pain' ? 'arwP' : e.style === 'ok' ? 'arwO' : 'arw'})"/>`}${labelHtml}</g>`;
}).join('\n');

const laneHtml = lanes.map((l, i) => {
  const cls = l.gap ? 'lane lane-gap' : 'lane';
  return `<g><rect x="${LANE_X}" y="${l.y}" width="${W - LANE_X - 40}" height="${l.h}" class="${cls}"/>` +
    `<text x="${LANE_X + 20}" y="${l.y + 34}" class="lane-t">${l.name}</text>` +
    `<text x="${LANE_X + 20}" y="${l.y + 54}" class="lane-s">${l.sub}</text></g>`;
}).join('\n');

const nodeHtml = nodes.map(n => `<g class="nd-g">${shape(n)}${textBlock(n)}${factChip(n)}</g>`).join('\n');

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="'Microsoft YaHei','PingFang SC','Noto Sans SC',sans-serif">
<defs>
  <marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="#4A5568"/>
  </marker>
  <marker id="arwP" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="#B4690E"/>
  </marker>
  <marker id="arwO" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="#1565C0"/>
  </marker>
  <style>
    .bg{fill:#FFFFFF}
    .lane{fill:#F7F9FC;stroke:#DDE3EC;stroke-width:1}
    .lane-gap{fill:#FDF7F7;stroke:#E8D3D3;stroke-dasharray:5 4}
    .lane-t{font-size:14px;font-weight:700;fill:#1A237E}
    .lane-s{font-size:11.5px;fill:#4E5A6B}
    .nd-s{fill:#FFFFFF;stroke:#1565C0;stroke-width:1.3}
    .nd-d{fill:#FFF8E8;stroke:#B4690E;stroke-width:1.4}
    .nd-start{fill:#1565C0;stroke:#1565C0}
    .nd-end{fill:#1A237E;stroke:#1A237E}
    .nd-pain{fill:#FDF0EE;stroke:#C0392B;stroke-width:1;stroke-dasharray:4 3}
    .tx-t{fill:#1B2430;font-weight:600}
    .tx-s{font-size:11px;fill:#4E5A6B}
    .tx-sd{font-size:11px;fill:#E3EEFB}
    .chip{fill:#EDF2FA;stroke:#C9D8EC;stroke-width:0.8}
    .chip-t{font-size:9px;fill:#2C5A96;font-weight:600}
    .eg{fill:none;stroke:#4A5568;stroke-width:1.4}
    .eg-dash{stroke-dasharray:5 4}
    .eg-pain{stroke:#B4690E}
    .eg-ok{stroke:#1565C0;stroke-width:1.6}
    .lb{font-size:10px;fill:#4A5568;text-anchor:middle;font-weight:600}
    .lb-bg{fill:#FFFFFF}
    .ttl{font-size:26px;font-weight:700;fill:#1A237E}
    .stl{font-size:13px;fill:#5A6474}
    .lg{font-size:11.5px;fill:#4A5568}
  </style>
</defs>
<rect width="${W}" height="${H}" class="bg"/>

${laneHtml}
${edgeHtml}
${nodeHtml}

<!-- 标题 -->
<text x="40" y="52" class="ttl">知行职业学院 · 实习反馈现状流程（As-Is）</text>
<text x="40" y="78" class="stl">主链路（访谈原文）：企业评分 → 教师回访 → 教务汇总 → 专业组评审　|　共 11 步，红色虚线框为访谈中明确出现的断点/异常</text>
<text x="40" y="100" class="stl">依据：discovery-report.json 访谈记录（education-fNNN 为事实编号）　·　试点范围：机电专业 5 家企业　·　每学期 600 名学生</text>

<!-- 图例 -->
<g transform="translate(${W - 470}, 150)">
  <rect x="0" y="0" width="430" height="58" rx="8" fill="#FFFFFF" stroke="#DDE3EC"/>
  <rect x="14" y="14" width="26" height="14" rx="3" fill="#FFFFFF" stroke="#1565C0" stroke-width="1.3"/>
  <text x="48" y="26" class="lg">正常步骤</text>
  <rect x="120" y="14" width="26" height="14" rx="0" fill="#FFF8E8" stroke="#B4690E" stroke-width="1.3" transform="translate(133,21) rotate(45) translate(-133,-21)"/>
  <text x="158" y="26" class="lg">判定</text>
  <rect x="205" y="14" width="26" height="14" rx="3" fill="#FDF0EE" stroke="#C0392B" stroke-dasharray="4 3"/>
  <text x="239" y="26" class="lg">断点/异常</text>
  <rect x="320" y="14" width="26" height="14" rx="3" fill="#1565C0"/>
  <text x="354" y="26" class="lg">起止</text>
  <text x="14" y="46" class="lg" style="font-size:10.5px;fill:#6B7686">灰色文字为访谈中"尚未核实"的责任归属，图上不作推断</text>
</g>
</svg>`;

require('fs').writeFileSync('D:/education_expense/output/flowchart/as-is-flow.svg', svg, 'utf8');
console.log('svg written', svg.length);
