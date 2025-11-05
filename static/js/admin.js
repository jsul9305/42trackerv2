let marathons = [];

const URL_TEMPLATES = {
  "Smartchip": "https://smartchip.co.kr/return_data_livephoto.asp?nameorbibno={nameorbibno}&usedata={usedata}",
  "SPCT": "http://time.spct.co.kr/m2.php?{usedata}&BIB_NO={nameorbibno}",
  "MyResult": "https://myresult.co.kr/{usedata}/{nameorbibno}",
  "TEST_MR": "http://localhost:5002/{usedata}/{nameorbibno}"
};

function $(id){ return document.getElementById(id); }
function val(id){ return $(id).value.trim(); }
function num(v, def){ const n = Number(v); return Number.isFinite(n) ? n : def; }
function toast(msg){ alert(msg); }

// 딥링크 빠른 이동
function openRaceLink(){
  const id = val('gotoId'); if(!id){ toast('마라톤 ID 입력'); return; }
  location.href = `/race/${encodeURIComponent(id)}`;
}
function copyRaceLink(){
  const id = val('gotoId'); if(!id){ toast('마라톤 ID 입력'); return; }
  const url = `${location.origin}/race/${id}`;
  navigator.clipboard.writeText(url).then(()=>toast('링크 복사됨')).catch(()=>prompt('복사 실패. 수동 복사:', url));
}

// URL 템플릿 검증
function checkTemplate(u){
  return u.includes('{nameorbibno}') && u.includes('{usedata}');
}

/* 1) 새 대회 추가 */
async function createMarathon(){
  const name = val('new_name');
  const total = num(val('new_total'), 21.1);
  const refresh = Math.max(5, num(val('new_refresh'), 60));
  const usedata = val('new_usedata') || null;
  const url = val('new_url');
  const event_date = val('new_event_date') || null;
  const gpx_file_input = $('new_gpx_file');
  const gpx_file = gpx_file_input.files[0];

  if(!name){ toast('대회명 필수'); return; }
  if(!url || !checkTemplate(url)){ toast('URL 템플릿에 {nameorbibno}, {usedata} 포함해야 합니다'); return; }

  const formData = new FormData();
  formData.append('name', name);
  formData.append('total_distance_km', total);
  formData.append('refresh_sec', refresh);
  if (usedata) formData.append('usedata', usedata);
  formData.append('url_template', url);
  if (event_date) formData.append('event_date', event_date);
  if (gpx_file) {
    formData.append('gpx_file', gpx_file);
  }

  const r = await fetch('/api/marathons', {
    method:'POST',
    body: formData
  });

  if(r.ok){
    $('new_name').value=''; $('new_total').value='21.1';
    $('new_refresh').value='60'; $('new_usedata').value=''; $('new_url').value='';
    gpx_file_input.value = ''; // Clear the file input
    await loadAll(); toast('대회 추가 완료');
  } else {
    const t = await r.text().catch(()=> '오류'); toast('추가 실패\n'+t);
  }
}

/* 2) 대회 리스트 로드 & 렌더 */
async function loadAll(){
  const r = await fetch('/api/marathons'); marathons = await r.json();
  
  const select = $('marathon-select');
  select.innerHTML = '';
  if(!marathons.length){
    select.innerHTML = '<option value="">등록된 대회가 없습니다</option>';
  } else {
    // 그룹 선택을 위해 마라톤 목록을 먼저 로드
    let groups = [];
    for(const m of marathons) {
        const groupRes = await fetch(`/api/marathons/${m.id}/groups`);
        const marathonGroups = await groupRes.json();
        groups = groups.concat(marathonGroups.map(g => ({...g, marathon_name: m.name})));
    }

    if(!groups.length) {
        select.innerHTML = '<option value="">등록된 그룹이 없습니다</option>';
    } else {
        select.innerHTML = '<option value="">그룹 선택</option>';
        for(const g of groups) {
            select.innerHTML += `<option value="${g.id}">${g.marathon_name} - ${escapeHtml(g.name)} (ID: ${g.id})</option>`;
        }
    }
  }

  renderList();
  const mid = new URLSearchParams(location.search).get('marathon_id');
  if(mid){ const el = document.querySelector(`[data-mid="${mid}"] details`); if(el) el.open = true; }
}

function renderList(){
  const wrap = $('list'); wrap.innerHTML = '';
  if(!marathons.length){
    wrap.innerHTML = '<div class="card small muted">등록된 대회가 없습니다.</div>'; return;
  }
  for(const m of marathons){
    const card = document.createElement('div');
    card.className = 'card'; card.dataset.mid = m.id;

    card.innerHTML = `
      <h3>${m.name}</h3>
      <div class="small">
        <span class="tag">ID ${m.id}</span>
        <span class="tag">${m.enabled ? '활성' : '비활성'}</span>
        <span class="tag">${m.total_distance_km}km</span>
        <span class="tag">${m.refresh_sec}s</span>
        ${m.event_date ? `<span class="tag" style="color:var(--accent2)">${m.event_date}</span>` : ''}
      </div>

      <div class="row" style="margin-top:10px; gap:10px;">
        <a class="btn block" href="/race/${m.id}">사용자 화면 열기</a>
        <a class="btn block" href="/race/${m.id}/map" target="_blank">전체 지도 보기</a>
        <button class="btn ghost block" onclick="copyLink(${m.id})">링크 복사</button>
      </div>

      <details style="margin-top:10px;">
        <summary>설정 편집 / 참가자 관리</summary>

        <div class="two" style="margin-top:8px;">
          <div class="field">
            <label>대회명</label>
            <input class="input" id="name_${m.id}" value="${escapeHtml(m.name)}" />
          </div>
          <div class="field">
            <label>총거리 (km)</label>
            <input class="input" id="total_${m.id}" type="number" inputmode="decimal" value="${m.total_distance_km}" />
          </div>
        </div>

        <div class="two" style="margin-top:8px;">
          <div class="field">
            <label>크롤 주기 (초)</label>
            <input class="input" id="refresh_${m.id}" type="number" inputmode="numeric" value="${m.refresh_sec}" />
          </div>
          <div class="field">
            <label>usedata (대회 ID)</label>
            <input class="input mono" id="usedata_${m.id}" value="${m.usedata ?? ''}" />
          </div>
          <div class="field">
            <label>대회 날짜 (선택)</label>
            <input class="input" id="event_date_${m.id}" type="date" value="${m.event_date ?? ''}" />
          </div>
          <div class="field">
            <label>GPX 파일 (코스 경로)</label>
            <input class="input" id="gpx_file_${m.id}" type="file" accept=".gpx" />
          </div>
        </div>

        <div class="field" style="margin-top:8px;">
          <label>URL 템플릿</label>
          ${getUrlTemplateSelect(`url_${m.id}`, m.url_template)}
          <div class="small muted">예: https://smartchip.co.kr/return_data_livephoto.asp?nameorbibno={nameorbibno}&usedata={usedata}</div>
        </div>

        <div class="row" style="margin-top:10px;">
          <select id="enabled_${m.id}" class="input" style="max-width:160px;">
            <option value="1" ${m.enabled? 'selected':''}>활성</option>
            <option value="0" ${!m.enabled? 'selected':''}>비활성</option>
          </select>
          <button class="btn primary" onclick="saveMarathon(${m.id})">저장</button>
        </div>

        <div class="row" style="margin-top:10px;">
            <div class="field">
                <label>참여 코드</label>
                <input class="input mono" id="code_${m.id}" value="${escapeHtml(m.join_code ?? '')}" readonly/>
            </div>
            <button class="btn ghost block" onclick="copyCode(${m.id})">코드 복사</button>
            <button class="btn ghost block" onclick="regenerateCode(${m.id})">코드 재생성</button>
        </div>

        <div style="height:8px"></div>
        <hr style="border:0; border-top:1px solid var(--border);" />

        <div id="groups_container_${m.id}"></div>

      </details>
    `;

    wrap.appendChild(card);
    loadGroupsForMarathon(m.id);
  }
}

function getUrlTemplateSelect(id, selectedValue) {
  let options = '';
  for (const name in URL_TEMPLATES) {
    const value = URL_TEMPLATES[name];
    const selected = (value === selectedValue) ? 'selected' : '';
    options += `<option value="${escapeHtml(value)}" ${selected}>${name}</option>`;
  }
  // Add an option for the current value if it's not in the standard list
  if (!Object.values(URL_TEMPLATES).includes(selectedValue)) {
      options += `<option value="${escapeHtml(selectedValue)}" selected>Custom</option>`;
  }
  return `<select class="input mono" id="${id}">${options}</select>`;
}

async function loadGroupsForMarathon(marathonId) {
    const container = $(`groups_container_${marathonId}`);
    const groupRes = await fetch(`/api/marathons/${marathonId}/groups`);
    const groups = await groupRes.json();
    container.innerHTML = '<h4>그룹 목록</h4>';

    if (!groups.length) {
        container.innerHTML += '<div class="small muted">등록된 그룹이 없습니다.</div>';
    }

    groups.forEach(g => {
        const groupEl = document.createElement('div');
        groupEl.className = 'group-card';
        groupEl.innerHTML = `
            <h5>${g.name} (ID: ${g.id}) - 코드: <code>${g.join_code}</code></h5>
            <div class="two" style="margin-top:6px;">
              <div class="field">
                <label>성명(표시용, 선택)</label>
                <input class="input" id="palias_${g.id}" placeholder="홍길동 (선택)" />
              </div>
              <div class="field">
                <label>배번/이름 (nameorbibno)</label>
                <input class="input" id="pbib_${g.id}" placeholder="예: 10396 또는 홍길동" />
              </div>
            </div>
            <div class="row" style="margin-top:6px;">
              <button class="btn primary" onclick="addParticipant(${g.id})">+ 참가자 추가</button>
            </div>
            <div id="plist_${g.id}" class="plist"></div>
        `;
        container.appendChild(groupEl);
        reloadParticipants(g.id);
    });
}

function escapeHtml(s){
  return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#039;");
}

function copyLink(mid){
  const url = `${location.origin}/race/${mid}`;
  navigator.clipboard.writeText(url).then(()=>alert('링크 복사됨')).catch(()=>prompt('복사 실패. 수동 복사:', url));
}
function copyCode(mid) {
  const v = val(`code_${mid}`);
  if(!v){ return toast('코드가 비어 있습니다. 재생성부터 하세요.'); }
  navigator.clipboard.writeText(v)
    .then(()=>toast('코드 복사됨'))
    .catch(()=>prompt('복사 실패. 수동 복사:', v));
}

async function regenerateCode(mid) {
  try{
    const r = await fetch(`/api/marathons/${mid}/regenerate_code`, { method:'POST' });
    const d = await r.json();
    if(!r.ok || !d.join_code){ return toast(d.description || d.error || '코드 재생성 실패'); }
    const input = $(`code_${mid}`);
    if (input) input.value = d.join_code;
    toast(`새 코드: ${d.join_code}`);
  }catch(e){
    toast('네트워크 오류');
  }
}

async function saveMarathon(mid){
  const name = val(`name_${mid}`);
  const total = num(val(`total_${mid}`), 21.1);
  const refresh = Math.max(5, num(val(`refresh_${mid}`), 60));
  const usedata = val(`usedata_${mid}`) || null;
  const url = val(`url_${mid}`);
  const enabled = Number(val(`enabled_${mid}`)||'1');
  const event_date = val(`event_date_${mid}`) || null;
  const gpx_file_input = $(`gpx_file_${mid}`);
  const gpx_file = gpx_file_input.files[0];

  if(!name){ toast('대회명 필수'); return; }
  if(!url || !checkTemplate(url)){ toast('URL 템플릿에 {nameorbibno}, {usedata} 포함해야 합니다'); return; }

  const formData = new FormData();
  formData.append('name', name);
  formData.append('total_distance_km', total);
  formData.append('refresh_sec', refresh);
  if (usedata) formData.append('usedata', usedata);
  formData.append('url_template', url);
  formData.append('enabled', enabled);
  if (event_date) formData.append('event_date', event_date);
  if (gpx_file) {
    formData.append('gpx_file', gpx_file);
  }

  const r = await fetch(`/api/marathons/${mid}`, {
    method:'PUT',
    body: formData
  });

  if(r.ok){ await loadAll(); toast('저장 완료'); }
  else{ const t = await r.text().catch(()=> '오류'); toast('저장 실패\n'+t); }
}

async function reloadParticipants(groupId){
  const r = await fetch(`/api/participants?group_id=${groupId}`);
  const list = await r.json();
  const box = $(`plist_${groupId}`); box.innerHTML = '';
  if(!list.length){
    box.innerHTML = '<div class="small muted">등록된 참가자가 없습니다.</div>'; return;
  }
  for(const p of list){
    const div = document.createElement('div');
    div.className = 'pitem';
    div.innerHTML = `
      <div>
        <div><b>${escapeHtml(p.alias || '-')}</b> <span class="tag mono">#${escapeHtml(p.nameorbibno)}</span></div>
        <div class="small muted">ID ${p.id} · active=${p.active}</div>
      </div>
      <div class="row">
        <button class="btn danger" onclick="delParticipant(${p.id}, ${groupId})">삭제</button>
      </div>
    `;
    box.appendChild(div);
  }
}

async function addParticipant(groupId){
  const alias = val(`palias_${groupId}`);
  const nameorbibno = val(`pbib_${groupId}`);
  if(!nameorbibno){ toast('배번/이름은 필수'); return; }
  const r = await fetch('/api/participants', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ group_id: groupId, alias, nameorbibno })
  });
  if(r.ok){ $(`pbib_${groupId}`).value=''; $(`palias_${groupId}`).value=''; await reloadParticipants(groupId); toast('추가 완료'); }
  else{ const t=await r.text().catch(()=> '오류'); toast('추가 실패\n'+t); }
}

async function delParticipant(pid, groupId){
  if(!confirm('정말 삭제할까요?')) return;
  await fetch(`/api/participants/${pid}`, {method:'DELETE'});
  await reloadParticipants(groupId);
}

function populateNewUrlSelect() {
  const select = $('new_url');
  if (!select) return;
  select.innerHTML = '';
  for (const name in URL_TEMPLATES) {
    const value = URL_TEMPLATES[name];
    select.innerHTML += `<option value="${escapeHtml(value)}">${name}</option>`;
  }
}

loadAll();
populateNewUrlSelect();

$('upload-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const formData = new FormData(form);
  const groupId = formData.get('marathon_id'); // This is now group_id
  const file = formData.get('file');

  if (!groupId) {
    toast('업로드할 그룹을 선택해주세요.');
    return;
  }
  if (!file || file.size === 0) {
    toast('업로드할 엑셀 파일을 선택해주세요.');
    return;
  }
  
  // FormData에 group_id를 명시적으로 설정
  formData.set('group_id', groupId);
  formData.delete('marathon_id');

  const r = await fetch('/api/participants/upload_excel', { method: 'POST', body: formData });
  const result = await r.json();
  toast(result.message || (result.error ? `오류: ${result.error}`: '알 수 없는 응답'));
  if(r.ok) await reloadParticipants(groupId);
});