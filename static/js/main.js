// ====== 상단 기존 전역/유틸 유지 ======
let REFRESH = 30, timer = null;
let marathons = [];
let currentMarathon = null;
let items = []; // 참가자 목록(선택된 대회)
let groups = [];

// ====== 코드 검증용 엔드포인트(그룹 → 대회 순) ======
const GROUP_VALIDATE_ENDPOINTS = [
  '/api/groups/validate',
  '/api/groups/code/validate'
];
const MARATHON_VALIDATE_ENDPOINTS = [
  '/api/join-code/validate',      // 앞서 만들어둔 후보들
  '/api/marathons/validate_code',
  '/api/marathons/code/validate',
  '/api/validate_code'
];

function getPred(last){
  if(!last) return null;
  return last.prediction || last.pred || null;
}
/* ===== Theme handling ===== */
const THEME_KEY = 'sc_theme';
function applyTheme(theme){
  const html = document.documentElement;
  html.setAttribute('data-theme', theme);
  const meta = document.querySelector('meta[name="theme-color"]');
  if(meta){ meta.setAttribute('content', theme==='dark' ? '#111827' : '#f7fafc'); }
  const btn = document.getElementById('themeBtn');
  if(btn){
    btn.setAttribute('aria-pressed', theme==='dark' ? 'true':'false');
    btn.textContent = theme==='dark' ? '🌙 다크' : '🌞 라이트';
  }
  localStorage.setItem(THEME_KEY, theme);
}
function initTheme(){
  const saved = localStorage.getItem(THEME_KEY);
  const sysDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(saved || (sysDark ? 'dark' : 'light'));
}
document.addEventListener('click', (e)=>{
  if(e.target && e.target.id === 'themeBtn'){
    const cur = document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(cur === 'dark' ? 'light' : 'dark');
  }
});

/* ===== Common ===== */
function $(id){ return document.getElementById(id); }

function lastPointLabel(last){
  const L = last?.splits?.length||0;
  if(!L) return null;
  const s = last.splits[L-1];
  return (s.point_label || s.point || null);
}
function lastPassClock(last){
  const L = last?.splits?.length||0;
  if(!L) return null;
  const s = last.splits[L-1];
  const v = (s.pass_clock || '').trim();
  return v || null;
}

// 5초 버퍼용: "HH:MM:SS" → +5초 → "HH:MM:SS"
function addSec(hms, add=5){
  if(!hms) return null;
  const m = /^(\d{1,2}):([0-5]?\d):([0-5]?\d)$/.exec(hms.trim());
  if(!m) return null;
  let h=+m[1], mi=+m[2], s=+m[3] + add;
  mi += Math.floor(s/60); s%=60;
  h  += Math.floor(mi/60); mi%=60;
  h%=24;
  return `${h.toString().padStart(2,'0')}:${mi.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
}

// 마지막 스플릿 포인트 라벨만
function lastPointLabel(last){
  const L = last?.splits?.length||0;
  if(!L) return null;
  const s = last.splits[L-1];
  return (s.point_label || s.point || null);
}

// --- 정렬 유틸 ---
function kmFromLabel(lbl){
  if(!lbl) return null;
  const m = /([0-9]+(?:\.[0-9]+)?)\s*km/i.exec(lbl);
  return m ? parseFloat(m[1]) : null;
}
function secFromClock(hms){
  if(!hms) return null;
  const m = /^(\d{1,2}):([0-5]?\d):([0-5]?\d)$/.exec(hms.trim());
  if(!m) return null;
  return (+m[1])*3600 + (+m[2])*60 + (+m[3]);
}
function secFromNet(net){
  if(!net) return null;
  const p = net.trim().split(':').map(x=>+x);
  if(p.length===3) return p[0]*3600 + p[1]*60 + p[2];
  if(p.length===2) return p[0]*60 + p[1];
  return null;
}
function lastSplit(last){
  if(!last || !last.splits || !last.splits.length) return null;
  return last.splits[last.splits.length-1];
}
function lastKm(last){
  const s = lastSplit(last); if(!s) return -1; // 시작 전은 -1로 끝으로 밀기
  if (s.point_km != null) return Number(s.point_km);
  const k = kmFromLabel(s.point_label || s.point);
  return (k!=null ? k : -1);
}
function lastClockSec(last){
  const s = lastSplit(last); if(!s) return Number.POSITIVE_INFINITY;
  const t = secFromClock(s.pass_clock);
  return (t!=null ? t : Number.POSITIVE_INFINITY);
}
function lastNetSec(last){
  const s = lastSplit(last); if(!s) return Number.POSITIVE_INFINITY;
  const t = secFromNet(s.net_time);
  return (t!=null ? t : Number.POSITIVE_INFINITY);
}
/* 정렬 기준: 
   1. 완주 여부 (완주자 우선)
   2. 이동 거리 (내림차순)
   3. 완주 기록 (오름차순, 완주자에게만 유효)
   4. 마지막 통과 시각 (오름차순)
   5. 이름 (오름차순)
*/
function compareParticipantFast(a, b){  
  const la = a._last || {}, lb = b._last || {};
  const pa = getPred(la), pb = getPred(lb);               // ✅ 추가
  const fa = (pa && pa.finished) ? 1 : 0;                  // ← la.pred → pa
  const fb = (pb && pb.finished) ? 1 : 0;                  // ← lb.pred → pb
  if (fa !== fb) return fb - fa; // 1. 완주자 우선

  const ka = lastKm(la), kb = lastKm(lb);
  if (ka !== kb) return kb - ka; // 2. 더 멀리 간 순서

  // 완주한 경우, net_time (완주 기록)으로 우선 정렬
  if (fa && fb) {
    const na = lastNetSec(la), nb = lastNetSec(lb);
    if (na !== nb) return na - nb; // 3. 완주 기록 빠른 순
  }

  const ca = lastClockSec(la), cb = lastClockSec(lb);
  if (ca !== cb) return ca - cb; // 4. 통과 시각 빠른 순

  return (a.alias||'').localeCompare(b.alias||'');
}


/* ========== 참여 코드 처리 (▶ 추가) ========== */

// 서버 검증 엔드포인트 후보들(환경 따라 다를 수 있어 순차 시도)
const CODE_VALIDATE_ENDPOINTS = [
  '/api/join-code/validate',
  '/api/code/validate',
  '/api/codes/validate',
  '/api/validate_code'
];
// 공통 파서
function pickBool(obj, keys){ for(const k of keys){ if(k in obj) return !!obj[k]; } return false; }
function pickStr(obj, keys){ for(const k of keys){ const v=obj[k]; if(typeof v==='string'&&v.trim()) return v.trim(); } return ''; }
async function tryValidate(endpoints, code){
  let lastErr = '';
  for(const url of endpoints){
    try{
      const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ code })});
      let data=null; try{ data = await res.clone().json(); }catch(_){}
      const ok = (data && pickBool(data, ['valid','ok','success'])) || (res.ok && !data);
      if(ok) return { ok:true, data: data||{} };
      let msg = data ? pickStr(data, ['message','error','detail','reason','description','msg']) : '';
      if(!msg){ try{ const t = await res.clone().text(); if(t && t.trim()) msg = t.trim().slice(0,300);}catch(_){ } }
      lastErr = msg || res.statusText || '유효성 검사 실패';
    }catch(e){ lastErr = e.message || String(e); }
  }
  return { ok:false, error:lastErr||'서버와 통신할 수 없습니다.' };
}

// ====== 참여 코드 제출: 그룹 → 대회 순으로 판별 ======
async function submitJoinCode(evt){
  if(evt) evt.preventDefault();
  const el = document.getElementById('joinCodeInput');
  const raw = (el?.value||'').trim(); if(!raw){ alert('참여 코드를 입력하세요.'); el?.focus(); return; }
  const code = raw.toUpperCase();

  // 1) 그룹 코드 우선 검사
  const g = await tryValidate(GROUP_VALIDATE_ENDPOINTS, code);
  if(g.ok){
    // data에 group_code/group_id가 있으면 좋지만 없어도 코드만으로 페이지 이동
    location.href = `/group/${encodeURIComponent(code)}`;
    return;
  }
  // 2) 대회 코드 검사
  const m = await tryValidate(MARATHON_VALIDATE_ENDPOINTS, code);
  if(m.ok){
    location.href = `/code/${encodeURIComponent(code)}`;
    return;
  }
  alert(`코드 확인 실패\n사유: ${g.error || m.error || '알 수 없음'}`);
}

// ====== 그룹 생성 ======
async function submitCreateGroup(evt){
  evt.preventDefault();
  const sel = document.getElementById('groupMarathonSelect');
  const nameEl = document.getElementById('groupNameInput');
  const marathon_id = Number(sel?.value||'');
  const group_name  = (nameEl?.value||'').trim();

  if(!marathon_id){ alert('대회를 선택하세요.'); sel?.focus(); return; }
  if(!group_name){ alert('그룹 이름을 입력하세요.'); nameEl?.focus(); return; }

  try{
    const r = await fetch('/api/groups', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ marathon_id, group_name })
    });
    const data = await r.json().catch(()=> ({}));
    if(!r.ok || data.success===false){
      const msg = data.error || data.message || '그룹 생성 실패';
      alert(msg);
      return;
    }
    // 기대 응답: {success:true, group_id, group_code}
    const code = data.group_code || '';
    if(code){
      if(confirm(`그룹이 생성되었습니다.\n참여코드: ${code}\n\n복사하시겠습니까?`)){
        try{ await navigator.clipboard.writeText(code); }catch(_){}
      }
      // 바로 그룹 페이지로 이동해도 되고, 유지해도 됨
      location.href = `/group/${encodeURIComponent(code)}`;
    }else{
      alert('그룹이 생성되었습니다. (참여코드 없음)'); // 방어처리
    }
  }catch(e){
    alert(`그룹 생성 실패: ${e.message||e}`);
  }
}

// ===== 그룹 목록 로딩 =====
async function loadGroups(params = {}){
  const qs = new URLSearchParams();
  if (params.marathon_id) qs.set('marathon_id', params.marathon_id);
  if (params.enabled_only) qs.set('enabled_only', '1');
  const url = '/api/groups' + (qs.toString() ? `?${qs.toString()}` : '');
  const r = await fetch(url);
  groups = await r.json();
  renderGroupList();
}

// ===== 그룹 리스트 렌더 =====
function renderGroupList(){
  const grid = document.getElementById('groupGrid');
  const search = (document.getElementById('groupSearch')?.value || '').trim().toLowerCase();
  if (!grid) return;

  grid.innerHTML = '';
  let list = groups.slice();

  if (search){
    list = list.filter(g => (g.name||'').toLowerCase().includes(search));
  }

  if (!list.length){
    grid.innerHTML = `<div class="card small muted">표시할 그룹이 없습니다.</div>`;
    return;
  }

  for (const g of list){
    const div = document.createElement('div');
    div.className = 'card';
    const code = g.group_code || '';
    div.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
        <h3 style="margin:0">${g.name}</h3>
        <span class="chip">${g.marathon_name || ('대회 #' + g.marathon_id)}</span>
        ${g.enabled ? '' : '<span class="chip" style="background:#555">비활성</span>'}
      </div>
      <div class="small" style="margin-top:6px;">
        <span class="muted">참여 코드:</span>
        ${code ? `<code>${code}</code>` : '<span class="muted">-</span>'}
        ${code ? `<button class="btn inline" data-copy="${code}">복사</button>
                  <a class="btn inline" href="/group/${encodeURIComponent(code)}">바로 입장</a>`
               : ''}
      </div>
    `;
    // 복사 핸들러
    div.querySelectorAll('button[data-copy]').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const c = btn.getAttribute('data-copy');
        navigator.clipboard.writeText(c)
          .then(()=> alert('참여 코드가 복사되었습니다.'))
          .catch(()=> prompt('복사 실패. 수동 복사:', c));
      });
    });

    grid.appendChild(div);
  }
}

// ===== 대회/그룹 셀렉트 채우기 (대회 로딩 후 호출) =====
function fillGroupMarathonSelects(){
  const selCreate = document.getElementById('groupMarathonSelect');
  const selFilter = document.getElementById('groupFilterMarathon');
  if (selCreate){
    selCreate.innerHTML = `<option value="">대회 선택…</option>`;
    for (const m of marathons){
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = `${m.name} (${m.total_distance_km}km)`;
      selCreate.appendChild(opt);
    }
  }
  if (selFilter){
    selFilter.innerHTML = `<option value="">전체 대회</option>`;
    for (const m of marathons){
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name;
      selFilter.appendChild(opt);
    }
  }
}

// ===== 이벤트 바인딩 =====
document.addEventListener('DOMContentLoaded', ()=>{
  // 검색
  const s = document.getElementById('groupSearch');
  if (s) s.addEventListener('input', renderGroupList);

  // 필터
  const f = document.getElementById('groupFilterMarathon');
  if (f) f.addEventListener('change', ()=>{
    const mid = Number(f.value || '');
    if (mid){
      loadGroups({ marathon_id: mid, enabled_only: 1 });
    } else {
      loadGroups({ enabled_only: 1 });
    }
  });
});

// ====== 기존 대회 목록 로딩 유지 + select 채우기 ======
async function loadMarathons(){
  const r = await fetch('/api/marathons');
  marathons = await r.json();
  renderMarathonList();
  fillGroupMarathonSelects();         // ← 추가
  await loadGroups({ enabled_only: 1 }); // ← 최초 그룹 목록 로딩
  if (window.INIT_MARATHON_ID) openRace(window.INIT_MARATHON_ID);
}

// ====== 초기 바인딩 ======
document.addEventListener('DOMContentLoaded', ()=>{
  const codeForm  = document.getElementById('codeForm');
  const groupForm = document.getElementById('groupCreateForm');
  if(codeForm)  codeForm.addEventListener('submit', submitJoinCode);
  if(groupForm) groupForm.addEventListener('submit', submitCreateGroup);
});

function pick(obj, keys) {
  for (const k of keys) {
    if (k in obj) return obj[k];
  }
  return undefined;
}

async function validateCodeOnServer(code){
  let lastErr = '';
  for (const url of CODE_VALIDATE_ENDPOINTS){
    try{
      const res = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ code })
      });
      // 200이 아니어도 본문에 이유가 있을 수 있으니 항상 파싱 시도
      let data = null;
      try { data = await res.clone().json(); } catch(_){}

      // 성공 판단
      const ok = (data ? pickBool(data, ['valid','ok','success']) : false) || (res.ok && !data);
      if (ok){
        return { ok: true, data: data||{} };
      }

      // 실패 메시지
      let msg = '';
      if (data) {
        msg = pickStr(data, ['message','error','detail','reason','description','msg']);
      }
      if (!msg){
        try{
          const text = await res.clone().text();
          if (text && text.trim()) msg = text.trim().slice(0, 300);
        }catch(_){}
      }
      if (!msg) msg = res.statusText || '유효성 검사 실패';
      lastErr = msg;
    }catch(e){
      lastErr = e.message || String(e);
      // 다음 후보 엔드포인트로 계속 시도
    }
  }
  return { ok:false, error: lastErr || '서버와 통신할 수 없습니다.' };
}


function renderMarathonList(){
  const g = $('marathonGrid'); g.innerHTML = '';
  if(!marathons.length){
    g.innerHTML = '<div class="card small muted">등록된 대회가 없습니다. 관리자에서 대회를 등록하세요.</div>';
    return;
  }
  for(const m of marathons){
    // ▶ 추가: 참여 코드 필드 추출(서버 키 이름 다양성 고려)
    const joinCode = (
      m.join_code ??
      m.participation_code ??
      m.invite_code ??
      m.code ??
      null
    );

    const div = document.createElement('div');
    div.className = 'card';

    // ▶ 추가: 참여 코드 표시/복사/딥링크
    const codeBlock = joinCode ? `
      <div class="small" style="margin-top:6px;">
        <span class="muted">참여 코드:</span>
        <code>${joinCode}</code>
        <button class="btn inline" data-copy="${joinCode}">복사</button>
        <a class="btn inline" href="/code/${encodeURIComponent(joinCode)}">코드로 이동</a>
      </div>
    ` : `
      <div class="small muted" style="margin-top:6px;">참여 코드가 아직 없습니다.</div>
    `;

    div.innerHTML = `
      <h3>${m.name}</h3>
      <div class="small muted">거리: ${m.total_distance_km}km · 새로고침: ${m.refresh_sec}s</div>
      ${codeBlock}
      <div style="margin-top:10px;">
        <a class="btn" style="width:100%; justify-content:center" href="/race/${m.id}">이 대회 보기</a>
      </div>
    `;

    // 복사 버튼 동작
    div.querySelectorAll('button[data-copy]').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const c = btn.getAttribute('data-copy');
        navigator.clipboard.writeText(c)
          .then(()=> alert('참여 코드가 복사되었습니다.'))
          .catch(()=> prompt('복사 실패. 수동 복사:', c));
      });
    });

    g.appendChild(div);
  }
}

function openRace(mid){
  currentMarathon = Number(mid);
  const m = marathons.find(x => x.id === currentMarathon);
  $('raceTitle').textContent = m ? m.name : `대회 #${currentMarathon}`;
  let metaText = m ? `ID ${m.id} · ${m.total_distance_km}km · ${m.refresh_sec}s` : '';
  if (m && m.event_date) metaText += ` · ${m.event_date}`;
  $('raceMeta').textContent = metaText;
  $('viewList').style.display = 'none';
  $('viewRace').style.display = 'block';
  $('fab').style.display = 'flex';
  loadParticipants();
}

function copyShare(){
  const url = `${location.origin}/race/${currentMarathon}`;
  navigator.clipboard.writeText(url).then(()=> alert('링크 복사됨')).catch(()=> prompt('링크 복사 실패. 수동 복사:', url));
}

/* ========== 참가자 & 그룹 렌더 ========== */
async function loadParticipants(){
  const r = await fetch('/api/participants?marathon_id='+currentMarathon);
  items = await r.json();
  await fetchAll();
  renderGroups();
  setupAutoRefresh(); // 첫 로딩 시 자동 새로고침 적용
}

async function fetchOne(p){
  const r = await fetch('/api/participant_data?participant_id='+p.id);
  const j = await r.json();
  p._last = j;
}

async function fetchAll(){
  const ps = items.map(p => fetchOne(p).catch(()=> p._last={msg:'로드 오류'}));
  await Promise.all(ps);
}

function groupOrder(name){
  // 1. 명시적 순서 정의 (Full, Half 등)
  const order = { 
    "Full": 1, "32K": 2, "Half": 3, 
    "10K": 4, "10km": 4, 
    "5K": 5, "5km": 5, 
    "3K": 6, "3km": 6,
    "미분류": 99
  };
  if (name in order) return order[name];

  // 2. 숫자 기반 종목명 처리 (e.g., "25km")
  const m = name.match(/^(\d+(?:\.\d+)?)/);
  if (m) return 10 - parseFloat(m[1]); // 숫자가 클수록 앞 순서 (10 - 25 = -15)

  // 3. 그 외
  return 90;
}

function lastSplitsText(last){
  if(!last || !last.splits || !last.splits.length) return '데이터 없음';
  const L = last.splits.length;
  const tail = last.splits.slice(Math.max(0, L-2)); // 최근 2개
  return tail.map(s => `${s.point_label||s.point}: ${s.net_time||s.time} (${s.pass_clock}|${s.pace})`).join('\n');
}

function allSplitsText(last){
  if(!last || !last.splits || !last.splits.length) return '데이터 없음';
  return last.splits.map(s => `${s.point_label||s.point}: ${s.net_time||s.time} (${s.pass_clock}|${s.pace})`).join('\n');
}

function lastPointLabel(last){
  const L = last?.splits?.length||0; if(!L) return null;
  const s = last.splits[L-1];
  return (s.point_label || s.point || null);
}
function lastPassClock(last){
  const L = last?.splits?.length||0; if(!L) return null;
  const v = (last.splits[L-1].pass_clock || '').trim();
  return v || null;
}
function lastNetTime(last){
  const L = last?.splits?.length||0; if(!L) return null;
  const v = (last.splits[L-1].net_time || '').trim();
  return v || null;
}

function renderGroups(){
  const wrap = $('groupContainer');
  wrap.innerHTML = '';

  // 종목 그룹핑
  const buckets = {};
  for (const it of items) {
    // 그룹명 결정: 1) 실시간 데이터의 race_label -> 2) 참가자 정보의 race_label -> 3) '미분류'
    const g = (it._last && it._last.race_label)
      ? it._last.race_label
      : (it.race_label || '미분류');

    (buckets[g] ||= []).push(it);
  }
  const names = Object.keys(buckets).sort((a,b)=> groupOrder(a)-groupOrder(b) || a.localeCompare(b));

  for(const gname of names){
    const list = buckets[gname];
    const sorted = list.slice().sort(compareParticipantFast);

    const sec = document.createElement('div');
    sec.className = 'section';

    const head = document.createElement('div');
    head.className = 'section-head';
    head.innerHTML = `<h2>${gname} (${sorted.length}명)</h2>`;
    const toggle = document.createElement('button');
    toggle.className = 'btn ghost toggle';
    toggle.textContent = '접기/펼치기';
    head.appendChild(toggle);
    sec.appendChild(head);

    /* ===== 모바일: 1줄 리스트(이름 · 현재 포인트 · 통과시각 · 타임 · 원문 · 삭제) ===== */
    const mobileWrap = document.createElement('div');
    mobileWrap.className = 'only-mobile compact-scroll';
    const mlist = document.createElement('div');
    mlist.className = 'mlist';

    for (const it of sorted){
      const last = it._last || {};
      const pt   = lastPointLabel(last) || '-';
      const clk  = lastPassClock(last)  || '-';  // PASS TIME(시계 시각)
      const net  = lastNetTime(last)    || '-';  // TIME(경과 시간)

      const row = document.createElement('div');
      row.className = 'mrow';
      row.innerHTML = `
        <span class="c name">${it.alias||'-'}</span>
        <span class="c pt">${pt}</span>
        <span class="c clock num" title="통과 시각(PASS TIME)">${clk}</span>
        <span class="c net num"   title="타임(TIME, 경과시간)">${net}</span>
        <span class="actions">
          ${last.url ? `<a class="btn inline" href="${last.url}" target="_blank">원문</a>` : `<span class="btn inline" style="opacity:.6;pointer-events:none">원문</span>`}
          <button class="btn inline" onclick="delRow(${it.id})">삭제</button>
        </span>
      `;
      mlist.appendChild(row);
    }
    mobileWrap.appendChild(mlist);
    sec.appendChild(mobileWrap);

    /* ===== 데스크톱 표(그대로 유지) ===== */
    const tblWrap = document.createElement('div');
    tblWrap.className = 'only-desktop';
    const tbl = document.createElement('table');
    tbl.className = 'table';
    tbl.innerHTML = `
      <thead>
        <tr>
          <th>성명</th><th>배번호/이름</th><th>포인트/시간</th>
          <th>상태</th><th>다음 포인트 ETA</th><th>피니시 ETA</th>
          <th>피니시 넷타임 예측</th><th>원문</th><th>삭제</th>
        </tr>
      </thead><tbody></tbody>
    `;
    const tb = tbl.querySelector('tbody');
    for(const it of sorted){
      const last = it._last || {};
      let pts = '데이터 없음';
      if(last.splits?.length){
        pts = last.splits.map(s => `${s.point_label||s.point}: ${s.net_time||s.time} (${s.pass_clock}|${s.pace})`).join('\n');
      }else if(last.msg){ pts = last.msg; }
      const pred = getPred(last);                                 // ✅ 추가
      const statusTxt = (pred && pred.finished) ? '완주' : ((last.splits && last.splits.length) ? '주행중' : '-');

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${it.alias||'-'}</td>
        <td>${it.nameorbibno||it.bib||'-'}</td>
        <td class="mono" style="white-space:pre; text-align:left">${pts}</td>
        <td>${statusTxt}</td>
        <td>${pred?.next_point_km ? (Number(pred.next_point_km).toFixed(1)+'km @ '+(pred.next_point_eta||'-')) : '-'}</td>
        <td>${pred?.finish_eta||'-'}</td>
        <td class="mono">${pred?.finish_net_pred||'-'}</td>
        <td>${last.url ? `<a href="${last.url}" target="_blank">원문</a>` : '-'}</td>
        <td><button class="btn inline" onclick="delRow(${it.id})">삭제</button></td>
      `;
      tb.appendChild(tr);
    }
    tblWrap.appendChild(tbl);
    sec.appendChild(tblWrap);

    // 접기/펼치기
    let collapsed = false;
    toggle.addEventListener('click', ()=>{
      collapsed = !collapsed;
      // 오타 수정: mobileList -> mobileWrap
      mobileWrap.style.display = collapsed ? 'none' : 'block';
      tblWrap.style.display = collapsed ? 'none' : 'block';
    });

    wrap.appendChild(sec);
  }
}
async function extractErrorMessage(res){
  // 우선 JSON 시도 -> 키 우선순위로 메시지 추출
  try{
    const data = await res.clone().json();
    const candKeys = ['message','error','detail','msg','reason','description'];
    for(const k of candKeys){
      if(data && typeof data[k] === 'string' && data[k].trim()) return data[k].trim();
    }
    if(typeof data === 'string' && data.trim()) return data.trim();
  }catch(_){/* pass */}
  // 텍스트로 재시도
  try{
    const text = await res.clone().text();
    if(text && text.trim()) return text.trim().slice(0, 300); // 너무 길면 컷
  }catch(_){/* pass */}
  return ''; // 정말 없으면 빈 문자열
}
/* ========== 동작 컨트롤 ========== */
async function addP(){
  if(!currentMarathon){ alert('대회를 먼저 선택하세요.'); return; }
  const alias = $('alias').value.trim();
  const nameorbibno = $('nameorbib').value.trim();
  if(!nameorbibno){ alert('배번/이름은 필수'); return; }

  try{
    const r = await fetch('/api/participants',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({marathon_id: currentMarathon, alias, nameorbibno})
    });

    // 서버 응답 바디를 한 번 확보 (성공/실패 모두)
    let data = null;
    try { data = await r.clone().json(); } catch(_){ /* JSON 아닐 수 있음 */ }

    // 실패 판단: 1) HTTP 실패  2) HTTP 200이라도 success=false
    const failed = !r.ok || (data && data.success === false);

    if(!failed){
      // 정상 성공
      $('nameorbib').value='';
      await loadParticipants();
      return;
    }

    // 실패 사유 구성
    let msg = '';
    if (data){
      msg = data.error || data.message || data.detail || data.msg || data.reason || data.description || '';
    }
    if (!msg){
      // 본문 키가 없거나 비어있으면 텍스트로 재시도
      try {
        const text = await r.clone().text();
        if (text && text.trim()) msg = text.trim().slice(0,300);
      } catch(_) {}
    }
    if (!msg){
      // 그래도 없으면 상태 텍스트라도
      msg = r.statusText || '원인 미상';
    }

    alert(`추가 실패 (HTTP ${r.status})\n사유: ${msg}`);
  }catch(e){
    alert(`추가 실패 (네트워크 오류)\n사유: ${e.message||e}`);
  }
}

async function delRow(id){
  try{
    const r = await fetch('/api/participants/'+id,{method:'DELETE'});
    let data = null;
    try { data = await r.clone().json(); } catch(_){}

    const failed = !r.ok || (data && data.success === false);
    if(!failed){
      await loadParticipants();
      return;
    }

    let msg = data?.error || data?.message || data?.detail || data?.msg || data?.reason || data?.description || '';
    if(!msg){
      try{
        const text = await r.clone().text();
        if(text && text.trim()) msg = text.trim().slice(0,300);
      }catch(_){}
    }
    if(!msg){ msg = r.statusText || '원인 미상'; }

    alert(`삭제 실패 (HTTP ${r.status})\n사유: ${msg}`);
  }catch(e){
    alert(`삭제 실패 (네트워크 오류)\n사유: ${e.message||e}`);
  }
}

function setupAutoRefresh(){
  if(timer) clearInterval(timer);
  timer = setInterval(async ()=>{ await fetchAll(); renderGroups(); }, REFRESH*1000);
}

// FAB segmented control
for(const b of document.querySelectorAll('.segbtn')){
  b.addEventListener('click', ()=>{
    for(const x of document.querySelectorAll('.segbtn')) x.classList.remove('active');
    b.classList.add('active');
    REFRESH = Number(b.dataset.sec||30);
    setupAutoRefresh();
  });
}
async function manualRefresh(){
  await fetchAll(); renderGroups();
}

/* CSV 다운로드 */
function downloadCSV(){
  const buckets = {};
  for(const it of items){
    const g = (it._last && it._last.group) ? it._last.group : '미분류';
    (buckets[g] ||= []).push(it);
  }
  const names = Object.keys(buckets).sort((a,b)=> groupOrder(a)-groupOrder(b) || a.localeCompare(b));

  const rows = [];
  for(const g of names){
    const sorted = buckets[g].slice().sort(compareParticipantFast);
    for(const it of sorted){
      const last = it._last || {};
      const name = it.alias||'-';
      const bib  = it.nameorbibno||it.bib||'-';
      const cols = [];
      if(last.splits && last.splits.length){
        for(const s of last.splits){ cols.push(`${s.point_label||s.point} ${s.net_time||s.time}`); }
        cols.push(last.pred?.finish_net_pred? `FINISH ${last.pred.finish_net_pred}` : 'FINISH -');
      }else{
        cols.push('데이터 없음');
      }
      rows.push([g, name, bib, ...cols]);
    }
  }
  const csv = rows.map(r => r.map(x => '"'+String(x).replaceAll('"','""')+'"').join(',')).join('\r\n');
  const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'smartchip_groups_sorted.csv'; a.click();
  URL.revokeObjectURL(url);
}

/* init */
initTheme();
loadMarathons();

