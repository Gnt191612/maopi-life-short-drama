// 人物建模审阅：three.js 离线小软件（模型以 base64 脚本形式内嵌，双击 html 即可用）
(() => {
'use strict';
const T = window.THREE, CAST = window.V11_CAST;
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const view = $('#view'), labels = $('#labels');
const renderer = new T.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(2, devicePixelRatio)); renderer.outputColorSpace = T.SRGBColorSpace;
renderer.toneMapping = T.AgXToneMapping; renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
view.prepend(renderer.domElement);
const scene = new T.Scene();
const pmrem = new T.PMREMGenerator(renderer); scene.environment = pmrem.fromScene(new T.RoomEnvironment(), 0.04).texture;
const camera = new T.PerspectiveCamera(30, 1, 0.02, 200);
const controls = new T.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.08; controls.target.set(0, 1, 0); camera.position.set(0, 1.1, 5.5);
const floor = new T.Mesh(new T.CircleGeometry(12, 64), new T.MeshStandardMaterial({ color: 0x8a8f94, roughness: 0.85 }));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
const lights = new T.Group(); scene.add(lights);

// ---------- 光照预设 ----------
function setLight(kind) {
  lights.clear();
  const add = l => { lights.add(l); return l; };
  const dir = (c, i, x, y, z, shadow) => { const l = add(new T.DirectionalLight(c, i)); l.position.set(x, y, z);
    if (shadow) { l.castShadow = true; l.shadow.mapSize.set(2048, 2048); const s = l.shadow.camera; s.left = -6; s.right = 6; s.top = 4; s.bottom = -1; l.shadow.bias = -0.0004; } return l; };
  if (kind === 'studio') { add(new T.HemisphereLight(0xffffff, 0x50555a, 0.55)); dir(0xffffff, 2.6, 2.5, 4, 4, true); dir(0xdde6ff, 0.9, -3, 2.5, 2.5); dir(0xffffff, 1.6, 0, 3.5, -4);
    scene.background = new T.Color(0xcfd6da); scene.environmentIntensity = 0.5; floor.material.color.set(0x8a8f94); }
  if (kind === 'day') { add(new T.HemisphereLight(0xbfdcff, 0x6b7a4a, 0.9)); dir(0xfff3df, 3.2, 4, 7, 3, true);
    scene.background = new T.Color(0xa9cdee); scene.environmentIntensity = 0.7; floor.material.color.set(0x7d8f63); }
  if (kind === 'indoor') { add(new T.HemisphereLight(0xffe6c8, 0x4a3b30, 0.6)); dir(0xffd9a8, 2.0, 1.5, 3, 2.5, true); add(new T.PointLight(0xffc98a, 6, 8)).position.set(-1.5, 2.4, 1.5);
    scene.background = new T.Color(0x6e5f52); scene.environmentIntensity = 0.35; floor.material.color.set(0x6b5442); }
  if (kind === 'night') { add(new T.HemisphereLight(0x3a4a7a, 0x101218, 0.35)); dir(0x9fb6ff, 0.9, -3, 5, 2, true); add(new T.PointLight(0xffb066, 12, 9)).position.set(1.6, 2.6, 1.8);
    scene.background = new T.Color(0x141a2a); scene.environmentIntensity = 0.12; floor.material.color.set(0x2b3038); }
}

// ---------- 模型加载 ----------
const loader = new T.GLTFLoader(), models = {}, loading = {};
const PART = [['strands', '头发'], ['scalpcap', '头皮'], ['high-poly', '眼睛'], ['eyebrow', '眉毛'], ['eyelash', '睫毛'], ['glasses', '眼镜'],
              ['button', '纽扣'], ['pocket', '口袋'], ['shoes', '鞋子'], ['suit', '衣服'], ['_body', '皮肤/身体']];
function partOf(o) { for (let p = o; p; p = p.parent) { const n = (p.name || '').toLowerCase(); for (const [k, v] of PART) if (n.includes(k.toLowerCase())) return v; } return '身体'; }
function loadScript(src) { return new Promise((ok, bad) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => bad(new Error('找不到 ' + src)); document.head.appendChild(s); }); }
async function getModel(id) {
  if (models[id]) return models[id];
  if (!loading[id]) loading[id] = (async () => {
    await loadScript('models/' + id + '.js');
    const b64 = window.V11_MODELS[id], bin = atob(b64), buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    delete window.V11_MODELS[id];
    const gltf = await new Promise((ok, bad) => loader.parse(buf.buffer, '', ok, bad));
    const root = gltf.scene; root.userData.id = id;
    root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.userData.part = partOf(o);
      const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach(m => { m.envMapIntensity = 0.6; if (o.userData.part === '头发' || o.userData.part === '头皮') m.side = T.DoubleSide; }); } });
    const box = new T.Box3().setFromObject(root); root.userData.h = box.max.y - box.min.y;
    models[id] = root; return root;
  })();
  return loading[id];
}

// ---------- 状态 ----------
let mode = 'single', current = 'lin', wire = false, hairOn = true, clothOn = true, rulerOn = false, marking = false, pending = null;
const placed = new T.Group(); scene.add(placed);
const offsetOf = id => mode === 'lineup' ? (CAST.findIndex(c => c.id === id) - 3) * 0.95 : 0;
function applyToggles() {
  placed.traverse(o => { if (!o.isMesh) return;
    const p = o.userData.part; o.visible = !((!hairOn && (p === '头发' || p === '头皮')) || (!clothOn && (p === '衣服' || p === '纽扣' || p === '口袋')));
    (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => m.wireframe = wire); });
  buildRuler();
}
async function show() {
  $('#loading').style.display = 'flex';
  const ids = mode === 'lineup' ? CAST.map(c => c.id) : [current];
  try {
    for (let i = 0; i < ids.length; i++) { $('#loading').textContent = '正在加载模型… ' + (i + 1) + '/' + ids.length; await getModel(ids[i]); }
  } catch (e) { $('#loading').textContent = '加载失败：' + e.message; return; }
  placed.clear();
  ids.forEach(id => { const m = models[id]; m.position.set(offsetOf(id), 0, 0); placed.add(m); });
  applyToggles(); $('#loading').style.display = 'none';
  $('#status').textContent = mode === 'lineup' ? '全员并排（点人物列表切换焦点）' : '当前：' + CAST.find(c => c.id === current).name;
}

// ---------- 视角 ----------
function setView(v, instant) {
  const m = models[current]; const h = m ? m.userData.h : 1.7, x0 = offsetOf(current);
  const P = { full: [0, h * 0.52, 0, 0, 1, h * 1.9 + 0.8], face: [0, h * 0.91, 0, 0, 1, 0.85], front: [0, h * 0.62, 0, 0, 1, 2.4],
              q34: [0, h * 0.85, 0, 0.6, 0.8, 1.3], side: [0, h * 0.75, 0, 1, 0, 1.9], back: [0, h * 0.7, 0, 0, -1, 2.2],
              top: [0, h * 0.5, 0, 0, 0.001, 0], feet: [0, 0.08, 0.04, 0.45, 0.9, 0.85], hands: [0.0, h * 0.47, 0, 0.55, 0.85, 1.0] }[v];
  if (!P) return;
  const t = new T.Vector3(x0 + P[0], P[1], P[2]);
  const d = v === 'top' ? new T.Vector3(t.x, h + 3.2, 0.01) : new T.Vector3(t.x + P[3] * P[5], t.y + (v === 'face' ? 0.02 : 0.05), t.z + P[4] * P[5]);
  if (mode === 'lineup' && v === 'full') { t.set(0, 0.9, 0); d.set(0, 1.2, 14.5); }   // 7 人并排全部入画
  tween(t, d, instant ? 0 : 450);
  $$('#views button').forEach(b => b.classList.toggle('on', b.dataset.view === v));
}
let tw = null;
function tween(t, d, ms) {
  const t0 = controls.target.clone(), d0 = camera.position.clone(), s = performance.now();
  tw = now => { const k = ms ? Math.min(1, (now - s) / ms) : 1, e = k * k * (3 - 2 * k);
    controls.target.lerpVectors(t0, t, e); camera.position.lerpVectors(d0, d, e); if (k >= 1) tw = null; };
}

// ---------- 身高尺 ----------
const ruler = new T.Group(); scene.add(ruler); let rulerTags = [];
function buildRuler() {
  ruler.clear(); rulerTags = []; if (!rulerOn) return;
  const x = offsetOf(current) - 0.45, mat = new T.MeshBasicMaterial({ color: 0x111111 });
  const bar = new T.Mesh(new T.BoxGeometry(0.008, 2.0, 0.008), mat); bar.position.set(x, 1.0, 0); ruler.add(bar);
  for (let i = 0; i <= 20; i++) { const len = i % 5 === 0 ? 0.08 : 0.04, tk = new T.Mesh(new T.BoxGeometry(len, 0.004, 0.004), mat);
    tk.position.set(x + len / 2, i * 0.1, 0); ruler.add(tk); if (i % 5 === 0) rulerTags.push([new T.Vector3(x + 0.1, i * 0.1, 0), (i / 10).toFixed(1) + ' m']); }
  const m = models[current]; if (m) { const hl = new T.Mesh(new T.BoxGeometry(0.5, 0.003, 0.003), new T.MeshBasicMaterial({ color: 0xd29922 }));
    hl.position.set(offsetOf(current) - 0.2, m.userData.h, 0); ruler.add(hl); rulerTags.push([new T.Vector3(x + 0.1, m.userData.h, 0), '身高 ' + m.userData.h.toFixed(2) + ' m']); }
}

// ---------- 意见标注 ----------
const KEY = 'v11_review_notes';
let notes = []; try { notes = JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { notes = []; }
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(notes)); } catch (e) { } renderNotes(); };
function region(y, h) { const r = y / h; return r > 0.87 ? '头部' : r > 0.80 ? '脖子/肩' : r > 0.52 ? '上身' : r > 0.45 ? '腰胯' : r > 0.06 ? '腿部' : '脚'; }
function noteText(n, i) { const c = CAST.find(c => c.id === n.cid);
  return `${i + 1}. 【${c ? c.name : n.cid}｜${n.region}｜${n.part}｜${n.side}】${n.text}  (位置 x=${n.p[0].toFixed(2)} y=${n.p[1].toFixed(2)} z=${n.p[2].toFixed(2)}，视角 ${n.view})`; }
function renderNotes() {
  $('#nCount').textContent = notes.length ? '(' + notes.length + ')' : '';
  $('#noteList').innerHTML = notes.map((n, i) => `<div class="note"><div class="meta"><span class="n">${i + 1}</span>${(CAST.find(c => c.id === n.cid) || {}).name || n.cid} · ${n.region} · ${n.part}<button data-del="${i}">删除</button><button data-go="${i}">查看</button></div>${n.text.replace(/</g, '&lt;')}</div>`).join('') || '<p class="hint">还没有意见。</p>';
}
$('#noteList').addEventListener('click', e => {
  const del = e.target.dataset.del, go = e.target.dataset.go;
  if (del !== undefined) { notes.splice(+del, 1); save(); }
  if (go !== undefined) { const n = notes[+go]; selectCast(n.cid).then(() => { const x0 = offsetOf(n.cid), t = new T.Vector3(n.p[0] + x0, n.p[1], n.p[2]);
    tween(t, t.clone().add(new T.Vector3(0.25, 0.05, 0.75)), 450); }); }
});
const ray = new T.Raycaster(), ndc = new T.Vector2(); let downAt = null;
function pick(ev) {
  const r = renderer.domElement.getBoundingClientRect(); ndc.set((ev.clientX - r.left) / r.width * 2 - 1, -(ev.clientY - r.top) / r.height * 2 + 1);
  ray.setFromCamera(ndc, camera); const hits = ray.intersectObjects(placed.children, true).filter(h => h.object.visible);
  return hits[0];
}
renderer.domElement.addEventListener('pointerdown', e => downAt = [e.clientX, e.clientY]);
renderer.domElement.addEventListener('pointerup', e => {
  if (!marking || !downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4 || e.button !== 0) return;
  const h = pick(e); if (!h) return;
  let root = h.object; while (root.parent && root.parent !== placed) root = root.parent;
  const id = root.userData.id, m = models[id], x0 = offsetOf(id), p = h.point.clone(); p.x -= x0;
  pending = { cid: id, p: [p.x, p.y, p.z], part: h.object.userData.part, region: region(p.y, m.userData.h),
              side: Math.abs(p.x) < 0.03 ? '中间' : (p.x > 0 ? '角色左侧' : '角色右侧'), view: ($$('#views button.on')[0] || {}).textContent || '自由' };
  showTab('notes'); $('#editor').style.display = 'block';
  $('#edTitle').textContent = `新意见：${CAST.find(c => c.id === id).name} · ${pending.region} · ${pending.part}`; $('#edText').value = ''; $('#edText').focus();
});
renderer.domElement.addEventListener('dblclick', e => { const h = pick(e); if (h) tween(h.point.clone(), camera.position.clone().sub(controls.target).add(h.point), 350); });
$('#edSave').onclick = () => { const t = $('#edText').value.trim(); if (!pending || !t) return; notes.push(Object.assign(pending, { text: t, time: new Date().toLocaleString() })); pending = null; $('#editor').style.display = 'none'; save(); toast('已保存'); };
$('#edCancel').onclick = () => { pending = null; $('#editor').style.display = 'none'; };
$('#copyAll').onclick = async () => {
  const txt = '【人物建模审阅意见】\n' + notes.map(noteText).join('\n');
  try { await navigator.clipboard.writeText(txt); toast('已复制 ' + notes.length + ' 条，直接粘贴到对话里即可'); }
  catch (e) { const ta = document.createElement('textarea'); ta.value = txt; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); toast('已复制'); }
};
$('#exportAll').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(notes, null, 1)], { type: 'application/json' }));
  a.download = '人物建模意见.json'; a.click(); };
$('#clearAll').onclick = () => { if (notes.length && confirm('清空全部 ' + notes.length + ' 条意见？')) { notes = []; save(); } };
function toast(t) { const el = $('#toast'); el.textContent = t; el.style.display = 'block'; clearTimeout(toast.h); toast.h = setTimeout(() => el.style.display = 'none', 2200); }

// ---------- 界面 ----------
function showTab(t) { $$('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === t)); $$('.tab').forEach(x => x.classList.toggle('on', x.id === 'tab-' + t)); }
$$('#tabs button').forEach(b => b.onclick = () => showTab(b.dataset.tab));
$('#castList').innerHTML = CAST.map(c => `<button class="cast" data-id="${c.id}"><b>${c.name}</b><small>${c.role}</small></button>`).join('');
async function selectCast(id) {
  current = id; $$('.cast').forEach(b => b.classList.toggle('on', b.dataset.id === id));
  const c = CAST.find(c => c.id === id);
  $('#info').innerHTML = [['身份', c.role], ['身高', c.height.toFixed(2) + ' m'], ['外形', c.look], ['服装', c.outfit], ['人物', c.note]].map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('');
  if (mode === 'single' || !models[id]) await show(); else { buildRuler(); $('#status').textContent = '全员并排 · 焦点：' + c.name; }
  setView(mode === 'lineup' ? 'front' : 'full');
}
$('#castList').addEventListener('click', e => { const b = e.target.closest('.cast'); if (b) selectCast(b.dataset.id); });
$$('#views button').forEach(b => b.onclick = () => setView(b.dataset.view));
$('#bSingle').onclick = () => { mode = 'single'; $('#bSingle').classList.add('on'); $('#bLineup').classList.remove('on'); show().then(() => setView('full')); };
$('#bLineup').onclick = () => { mode = 'lineup'; $('#bLineup').classList.add('on'); $('#bSingle').classList.remove('on'); show().then(() => setView('full')); };
$('#light').onchange = e => setLight(e.target.value);
const tog = (id, fn) => $(id).onclick = () => { const on = !$(id).classList.contains('on'); $(id).classList.toggle('on', on); fn(on); };
tog('#tHair', on => { hairOn = on; applyToggles(); }); tog('#tCloth', on => { clothOn = on; applyToggles(); });
tog('#tWire', on => { wire = on; applyToggles(); }); tog('#tRuler', on => { rulerOn = on; buildRuler(); });
tog('#tSpin', on => { controls.autoRotate = on; controls.autoRotateSpeed = 1.5; });
tog('#bMark', on => { marking = on; renderer.domElement.style.cursor = on ? 'crosshair' : ''; if (on) toast('在模型上点一下要提意见的位置'); });
$('#bShot').onclick = () => { renderer.render(scene, camera); const a = document.createElement('a'); a.href = renderer.domElement.toDataURL('image/png'); a.download = '人物截图_' + current + '.png'; a.click(); };

// ---------- 渲染循环 ----------
function resize() { const w = view.clientWidth, h = view.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
new ResizeObserver(resize).observe(view);
const v3 = new T.Vector3();
function overlay() {
  const w = view.clientWidth, h = view.clientHeight, html = [];
  const proj = p => { v3.copy(p).project(camera); return v3.z < 1 ? [(v3.x + 1) / 2 * w, (1 - v3.y) / 2 * h] : null; };
  notes.forEach((n, i) => { if (!placed.children.some(c => c.userData.id === n.cid)) return; const s = proj(new T.Vector3(n.p[0] + offsetOf(n.cid), n.p[1], n.p[2]));
    if (s) html.push(`<div class="pin" style="left:${s[0]}px;top:${s[1]}px">${i + 1}</div>`); });
  rulerTags.forEach(([p, t]) => { const s = proj(p); if (s) html.push(`<div class="ruler" style="left:${s[0]}px;top:${s[1]}px">${t}</div>`); });
  if (mode === 'lineup') CAST.forEach(c => { const m = models[c.id]; if (!m) return; const s = proj(new T.Vector3(offsetOf(c.id), m.userData.h + 0.12, 0));
    if (s) html.push(`<div class="lb" style="left:${s[0]}px;top:${s[1]}px">${c.name}</div>`); });
  labels.innerHTML = html.join('');
}
function loop(now) { requestAnimationFrame(loop); if (tw) tw(now); controls.update(); renderer.render(scene, camera); overlay(); }
setLight('studio'); renderNotes(); resize(); requestAnimationFrame(loop);
selectCast('lin');
})();
