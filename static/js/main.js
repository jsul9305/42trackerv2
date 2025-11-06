let REFRESH = 30;
let timer = null;
let allMarathons = [];
let allGroups = [];
let currentGroup = null;
let participants = [];
let map = null;
let splitPoints = {};
let runnerMarkers = {};

const $ = (id) => document.getElementById(id);

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    bindEventListeners();
    init();
});

async function init() {
    console.log(`Initializing with groupCode: '${window.INIT_GROUP_CODE}' and marathonId: '${window.INIT_MARATHON_ID}'`);
    await loadMarathons(); // Still need this for the <select> dropdown in the create form

    const groupCode = window.INIT_GROUP_CODE || null;
    const marathonId = window.INIT_MARATHON_ID || null;

    if (groupCode) {
        showGroupView(groupCode);
    } else {
        showGroupListView();
    }
}

function bindEventListeners() {
    $('themeBtn').addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
        applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
    });

    $('codeForm').addEventListener('submit', submitJoinCode);
    $('groupCreateForm').addEventListener('submit', submitCreateGroup);

    document.querySelectorAll('.segbtn').forEach(b => {
        b.addEventListener('click', () => {
            document.querySelectorAll('.segbtn').forEach(x => x.classList.remove('active'));
            b.classList.add('active');
            REFRESH = Number(b.dataset.sec || 30);
            setupAutoRefresh();
        });
    });
    const manualRefreshBtn = document.querySelector('#fab .btn:not(.segbtn)');
    if(manualRefreshBtn) {
        manualRefreshBtn.addEventListener('click', manualRefresh);
    }
}

async function api(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            const message = errorData?.error || errorData?.message || `HTTP error! status: ${response.status}`;
            throw new Error(message);
        }
        return response.json();
    } catch (error) {
        console.error('API Error:', error);
        alert(`Error: ${error.message}`);
        throw error;
    }
}

async function loadMarathons() {
    allMarathons = await api('/api/marathons');
    fillMarathonSelect();
}

async function loadAllGroups() {
    allGroups = await api('/api/groups');
    renderGroupList();
}

async function loadParticipants(groupId) {
    participants = await api(`/api/participants?group_id=${groupId}`);
    await fetchAllParticipantData();
    renderParticipantList();
    updateRunnerMarkers();
    setupAutoRefresh();
}

async function fetchAllParticipantData() {
    const promises = participants.map(p =>
        api(`/api/participant_data?participant_id=${p.id}`).then(data => {
            p._last = data;
        }).catch(() => {
            p._last = { msg: '로드 오류' };
        })
    );
    await Promise.all(promises);
}

function showView(viewId) {
    $('viewList').style.display = 'none';
    $('viewRace').style.display = 'none';
    $(viewId).style.display = 'block';
    
    $('fab').style.display = (viewId === 'viewRace') ? 'flex' : 'none';
}

async function showGroupListView() {
    showView('viewList');
    $('groupCreateForm').parentElement.style.display = 'block';
    $('codeForm').parentElement.style.display = 'block';
    await loadAllGroups();
}

async function showGroupView(groupCode) {
    showView('viewRace');
    $('groupCreateForm').parentElement.style.display = 'none';
    $('codeForm').parentElement.style.display = 'none';
    try {
        const result = await api('/api/groups/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ join_code: groupCode })
        });

        if (!result.valid) {
            alert('유효하지 않은 그룹 코드입니다.');
            showGroupListView();
            return;
        }
        
        currentGroup = result.group;
        
        $('raceTitle').textContent = `${currentGroup.marathon_name} @ ${currentGroup.name}`;
        document.title = `${currentGroup.marathon_name} @ ${currentGroup.name}`;
        $('raceMeta').textContent = `참여 코드: ${currentGroup.join_code}`;

        const mapBtn = $('fullMapBtn');
        mapBtn.href = `/group/${currentGroup.join_code}/map`;
        mapBtn.style.display = 'inline-flex';
        
        // document.querySelector('#viewRace .card').style.display = 'none'; // This was hiding the "Add Participant" form.
        
        // Per user request, map is not needed on this page.
        // await initMap(currentGroup.marathon_id);
        $('map').style.display = 'none';


        await loadParticipants(currentGroup.id);

    } catch (error) {
        showGroupListView();
    }
}

async function submitJoinCode(event) {
    event.preventDefault();
    const input = $('joinCodeInput');
    const code = input.value.trim().toUpperCase();
    if (!code) return;

    try {
        const result = await api('/api/code/resolve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });

        if (result.type === 'group') {
            window.location.href = `/group/${result.group.join_code}`;
        } else if (result.type === 'marathon') {
            alert('이 코드는 마라톤 코드입니다. 그룹 참여 코드를 입력해주세요.');
        }
    } catch (error) {
        input.focus();
    }
}

async function submitCreateGroup(event) {
    event.preventDefault();
    const marathonSelect = $('groupMarathonSelect');
    const nameInput = $('groupNameInput');
    const marathon_id = marathonSelect.value;
    const name = nameInput.value.trim();

    if (!marathon_id) {
        alert('대회를 선택하세요.');
        return;
    }
    if (!name) {
        alert('그룹 이름을 입력하세요.');
        return;
    }

    try {
        const result = await api('/api/groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ marathon_id: Number(marathon_id), name })
        });

        if (result.success) {
            const code = result.group.join_code;
            if (confirm(`그룹 생성 완료!\n참여 코드: ${code}\n\n코드를 복사하시겠습니까?`)) {
                navigator.clipboard.writeText(code);
            }
            window.location.href = `/group/${code}`;
        }
    } catch (error) {
    }
}



async function deleteParticipant(participantId) {
    if (!confirm('정말로 이 참가자를 삭제하시겠습니까?')) return;
    try {
        await api(`/api/participants/${participantId}`, { method: 'DELETE' });
        await loadParticipants(currentGroup.id);
    } catch (error) {
    }
}

function renderGroupList() {
    const grid = $('groupGrid');
    grid.innerHTML = '';
    if (!allGroups.length) {
        grid.innerHTML = '<div class="card small muted">등록된 그룹이 없습니다. 새 그룹을 만들어보세요.</div>';
        return;
    }
    allGroups.forEach(g => {
        const div = document.createElement('div');
        div.className = 'card';
        div.style.cursor = 'pointer';
        div.innerHTML = `
            <h3>${g.marathon_name} @ ${g.name}</h3>
            <div class="small muted">참여 코드: ${g.join_code}</div>
        `;
        div.addEventListener('click', () => {
            const enteredCode = prompt(`'${g.name}' 그룹에 참여하려면 참여 코드를 입력하세요.`);
            if (enteredCode === null) { // User cancelled the prompt
                return;
            }
            
            if (enteredCode.trim().toUpperCase() === g.join_code.toUpperCase()) {
                window.location.href = `/group/${g.join_code}`;
            } else {
                alert('참여 코드가 일치하지 않습니다.');
            }
        });
        grid.appendChild(div);
    });
}



function fillMarathonSelect() {
    const select = $('groupMarathonSelect');
    select.innerHTML = '<option value="">대회 선택…</option>';
    allMarathons.forEach(m => {
        const option = document.createElement('option');
        option.value = m.id;
        option.textContent = m.name;
        select.appendChild(option);
    });
}

function renderParticipantList() {
    const wrap = $('groupContainer');
    wrap.innerHTML = '';

    const buckets = {};
    for (const it of participants) {
        const g = (it._last && it._last.race_label)
            ? it._last.race_label
            : (it.race_label || '미분류');
        (buckets[g] ||= []).push(it);
    }
    
    function groupOrder(name){
      const order = { "Full": 1, "32K": 2, "Half": 3, "10K": 4, "10km": 4, "5K": 5, "5km": 5, "3K": 6, "3km": 6, "미분류": 99 };
      if (name in order) return order[name];
      const m = name.match(/^(\d+(?:\.\d+)?)/);
      if (m) return 10 - parseFloat(m[1]);
      return 90;
    }

    const names = Object.keys(buckets).sort((a, b) => groupOrder(a) - groupOrder(b) || a.localeCompare(b));

    if (names.length === 0) {
        wrap.innerHTML = '<div class="card small muted">이 그룹에 등록된 참가자가 없습니다.</div>';
        return;
    }

    for (const gname of names) {
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

        const tblWrap = document.createElement('div');
        tblWrap.className = 'only-desktop';
        const tbl = document.createElement('table');
        tbl.className = 'table';
        tbl.innerHTML = `
            <thead>
                <tr>
                    <th>성명</th>
                    <th>배번호/이름</th>
                    <th style="width: 30%;">포인트/시간</th>
                    <th>상태</th>
                    <th>다음 ETA</th>
                    <th>피니시 ETA</th>
                    <th>피니시 예측</th>
                    <th>관리</th>
                </tr>
            </thead>
            <tbody></tbody>
        `;
        const tb = tbl.querySelector('tbody');
        for (const it of sorted) {
            const last = it._last || {};
            const splits = last.splits || [];
            const pred = getPred(last) || {};
            const statusTxt = pred.finished ? '완주' : (splits.length ? '주행중' : '대기');

            const splitsHtml = splits.map(s => {
                const interval = s.interval ? `(${s.interval})` : '';
                const net = s.net_time || '';
                const clock = s.pass_clock || '';
                return `<div>
                    <span class="split-label">${s.point_label || '-'}:</span>
                    <span class="split-time mono">${interval}</span>
                    <span class="split-net mono">${net}</span>
                    <span class="split-clock mono">@${clock}</span>
                </div>`;
            }).join('');

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${it.alias || it.nameorbibno}</td>
                <td>${it.nameorbibno || '-'}</td>
                <td class="splits-cell">${splitsHtml}</td>
                <td>${statusTxt}</td>
                <td class="mono">${pred.next_point_eta || '-'}</td>
                <td class="mono">${pred.finish_eta || '-'}</td>
                <td class="mono">${pred.finish_net_pred || '-'}</td>
                <td>
                    ${last.url ? `<a href="${last.url}" target="_blank" class="btn inline">원문</a>` : ''}
                    <button class="btn inline danger" onclick="deleteParticipant(${it.id})">삭제</button>
                </td>
            `;
            tb.appendChild(tr);
        }
        tblWrap.appendChild(tbl);
        sec.appendChild(tblWrap);
        
        const mobileWrap = document.createElement('div');
        mobileWrap.className = 'only-mobile compact-scroll';
        const mlist = document.createElement('div');
        mlist.className = 'mlist';
         for (const it of sorted) {
            const last = it._last || {};
            const pt = (last.splits && last.splits.length) ? (last.splits[last.splits.length-1].point_label || '-') : '-';
            const clk = (last.splits && last.splits.length) ? (last.splits[last.splits.length-1].pass_clock || '-') : '-';
            const net = (last.splits && last.splits.length) ? (last.splits[last.splits.length-1].net_time || '-') : '-';

            const row = document.createElement('div');
            row.className = 'mrow';
            row.innerHTML = `
                <span class="c name">${it.alias || it.nameorbibno}</span>
                <span class="c pt">${pt}</span>
                <span class="c clock num">${clk}</span>
                <span class="c net num">${net}</span>
                <span class="actions">
                    ${last.url ? `<a href="${last.url}" target="_blank" class="btn inline">원문</a>` : ''}
                    <button class="btn inline" onclick="deleteParticipant(${it.id})">삭제</button>
                </span>
            `;
            mlist.appendChild(row);
        }
        mobileWrap.appendChild(mlist);
        sec.appendChild(mobileWrap);

        let collapsed = false;
        toggle.addEventListener('click', () => {
            collapsed = !collapsed;
            tblWrap.style.display = collapsed ? 'none' : 'block';
            mobileWrap.style.display = collapsed ? 'none' : 'block';
        });

        wrap.appendChild(sec);
    }
}

function setupAutoRefresh() {
    if (timer) clearInterval(timer);
    if (currentGroup) {
        timer = setInterval(manualRefresh, REFRESH * 1000);
    }
}

async function manualRefresh() {
    if (!currentGroup) return;
    await fetchAllParticipantData();
    renderParticipantList();
    updateRunnerMarkers();
}

function initTheme() {
    const savedTheme = localStorage.getItem('sc_theme');
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    applyTheme(savedTheme || systemTheme);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    if (themeColorMeta) {
        themeColorMeta.setAttribute('content', theme === 'dark' ? '#111827' : '#f7fafc');
    }
    $('themeBtn').setAttribute('aria-pressed', theme === 'dark');
    $('themeBtn').textContent = theme === 'dark' ? '🌙 다크' : '🌞 라이트';
    localStorage.setItem('sc_theme', theme);
}
function getPred(last){
  if(!last) return null;
  return last.prediction || last.pred || null;
}
function lastSplit(last){
  if(!last || !last.splits || !last.splits.length) return null;
  return last.splits[last.splits.length-1];
}
function kmFromLabel(lbl){
  if(!lbl) return null;
  const m = /(\d+(?:\.\d+)?)\s*km/i.exec(lbl);
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
function lastKm(last){
  const s = lastSplit(last); if(!s) return -1;
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
function compareParticipantFast(a, b){  
  const la = a._last || {}, lb = b._last || {};
  const pa = getPred(la), pb = getPred(lb);
  const fa = (pa && pa.finished) ? 1 : 0;
  const fb = (pb && pb.finished) ? 1 : 0;
  if (fa !== fb) return fb - fa;

  const ka = lastKm(la), kb = lastKm(lb);
  if (ka !== kb) return kb - ka;

  if (fa && fb) {
    const na = lastNetSec(la), nb = lastNetSec(lb);
    if (na !== nb) return na - nb;
  }

  const ca = lastClockSec(la), cb = lastClockSec(lb);
  if (ca !== cb) return ca - cb;

  return (a.alias||'').localeCompare(b.alias||'');
}

function renderSplitPointMarkers() {
    if (!map) return;
    for (const label in splitPoints) {
        const coords = splitPoints[label];
        // Leaflet uses [lat, lon] but our GeoJSON is [lon, lat]
        L.marker([coords[1], coords[0]]).addTo(map)
            .bindPopup(label)
            .openPopup();
    }
}

function updateRunnerMarkers() {
    if (!map || !Object.keys(splitPoints).length) return;

    participants.forEach(p => {
        const last = p._last;
        if (!last || !last.splits || !last.splits.length) return;

        const lastSplit = last.splits[last.splits.length - 1];
        const splitLabel = lastSplit.point_label;

        if (splitPoints[splitLabel]) {
            const coords = splitPoints[splitLabel];
            const latLng = [coords[1], coords[0]]; // Leaflet is [lat, lon]
            
            if (runnerMarkers[p.id]) {
                runnerMarkers[p.id].setLatLng(latLng);
            } else {
                runnerMarkers[p.id] = L.marker(latLng, { 
                    icon: L.divIcon({
                        className: 'runner-icon',
                        html: `<div>${p.alias || p.nameorbibno}</div>`,
                        iconSize: [60, 20]
                    }) 
                }).addTo(map);
            }
            runnerMarkers[p.id].bindPopup(`<b>${p.alias || p.nameorbibno}</b><br>${splitLabel}`);
        }
    });
}

async function initMap(marathonId) {
    if (map) {
        map.remove();
        map = null;
    }
    // Clear old data
    splitPoints = {};
    Object.values(runnerMarkers).forEach(m => m.remove());
    runnerMarkers = {};
    
    try {
        const mapData = await api(`/api/marathons/${marathonId}/map_data`);
        
        if (mapData.course_geo_json) {
            $('map').style.display = 'block';
            const geoJsonFeature = mapData.course_geo_json;
            
            map = L.map('map');
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);
            
            const geoJsonLayer = L.geoJSON(geoJsonFeature).addTo(map);
            map.fitBounds(geoJsonLayer.getBounds());

            if (geoJsonFeature.properties && geoJsonFeature.properties.split_points) {
                splitPoints = geoJsonFeature.properties.split_points;
                renderSplitPointMarkers();
            }

        } else {
            // Hide map if no course data
            $('map').style.display = 'none';
        }
    } catch (error) {
        console.error("Failed to load map data", error);
        $('map').style.display = 'none';
    }
}