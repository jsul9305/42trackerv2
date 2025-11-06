document.addEventListener('DOMContentLoaded', () => {
    const marathonId = window.MARATHON_ID;
    if (marathonId) {
        initFullMap(marathonId);
    }
});

let map = null;
let currentCourse = null;
let runnerMarkers = {};
let participants = [];
let marathonData = null;

let REFRESH_INTERVAL = 1000;
let refreshTimer = null;

const $ = (selector) => document.querySelector(selector);

async function api(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function bindEventListeners() {
    $('#themeBtn').addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
        applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
    });

    document.querySelectorAll('.segbtn').forEach(b => {
        b.addEventListener('click', () => {
            document.querySelectorAll('.segbtn').forEach(x => x.classList.remove('active'));
            b.classList.add('active');
            REFRESH_INTERVAL = Number(b.dataset.sec || 1) * 1000;
            setupAutoRefresh();
        });
    });

    $('#manualRefreshBtn').addEventListener('click', manualRefresh);
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
    $('#themeBtn').setAttribute('aria-pressed', theme === 'dark');
    $('#themeBtn').textContent = theme === 'dark' ? '🌙 다크' : '🌞 라이트';
    localStorage.setItem('sc_theme', theme);
}

function setupAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    refreshTimer = setInterval(manualRefresh, REFRESH_INTERVAL);
    console.log(`Auto-refresh setup with interval: ${REFRESH_INTERVAL}ms`);
}

async function manualRefresh() {
    console.log('Refreshing participant data...');
    await refreshAllParticipantData(window.MARATHON_ID);
}

function clearMap() {
    if (map) {
        map.eachLayer(layer => {
            if (!!layer.toGeoJSON) { // It's a vector layer
                map.removeLayer(layer);
            }
        });
        // Also clear tile layers if you want to fully reset
    }
    runnerMarkers = {};
}

function renderCourse(course) {
    clearMap();
    currentCourse = course;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    if (course && course.course_geo_json) {
        const geoJsonFeature = course.course_geo_json;
        const geoJsonLayer = L.geoJSON(geoJsonFeature).addTo(map);
        map.fitBounds(geoJsonLayer.getBounds());

        if (geoJsonFeature.properties && geoJsonFeature.properties.split_points) {
            renderSplitPointMarkers(geoJsonFeature.properties.split_points);
        }
    }
    updateRunnerMarkers(); // Redraw runners on the new course
}

function createCourseSelector(courses) {
    const container = $('#course-selector-container');
    if (!courses || courses.length <= 1) {
        container.style.display = 'none';
        return;
    }

    const select = document.createElement('select');
    select.className = 'input';
    courses.forEach(course => {
        const option = document.createElement('option');
        option.value = course.id;
        option.textContent = course.name;
        select.appendChild(option);
    });

    select.addEventListener('change', (e) => {
        const selectedCourseId = parseInt(e.target.value, 10);
        const selectedCourse = marathonData.courses.find(c => c.id === selectedCourseId);
        if (selectedCourse) {
            renderCourse(selectedCourse);
        }
    });

    container.appendChild(select);
}

async function initFullMap(marathonId) {
    try {
        bindEventListeners();
        initTheme();

        marathonData = await api(`/api/marathons/${marathonId}/map_data`);

        map = L.map('map');

        if (marathonData.courses && marathonData.courses.length > 0) {
            createCourseSelector(marathonData.courses);
            renderCourse(marathonData.courses[0]); // Render the first course by default
        } else {
            // Handle case with no courses
            map.setView([37.5665, 126.9780], 13); // Default to Seoul
             L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);
        }

        await manualRefresh();
        setupAutoRefresh();

    } catch (error) {
        console.error('Map initialization failed:', error);
    }
}

async function refreshAllParticipantData(marathonId) {
    if (!marathonId) return;
    try {
        participants = await api(`/api/marathons/${marathonId}/participants`);
        const promises = participants.map(p =>
            api(`/api/participant_data?participant_id=${p.id}`).then(data => {
                p._last = data;
            }).catch(() => {
                p._last = { msg: '로드 오류' };
            })
        );
        await Promise.all(promises);
        updateRunnerMarkers();
    } catch (error) {
        console.error('Failed to refresh participant data:', error);
    }
}

function renderSplitPointMarkers(splitPoints) {
    if (!map) return;
    for (const label in splitPoints) {
        const coords = splitPoints[label];
        L.marker([coords[1], coords[0]], {
            icon: L.divIcon({
                className: 'split-point-icon',
                html: `<div>${label}</div>`,
                iconSize: [40, 20]
            })
        }).addTo(map);
    }
}

function updateRunnerMarkers() {
    if (!map || !currentCourse || !currentCourse.course_geo_json) return;

    const splitPoints = currentCourse.course_geo_json.properties.split_points || {};
    const activeRunners = new Set();

    const runnerIcon = L.icon({
        iconUrl: '/static/icons/marker.png',
        iconSize: [30, 42],
        iconAnchor: [15, 42],
    });

    participants.forEach(p => {
        activeRunners.add(p.id);
        const last = p._last;
        let latLng = null;

        if (last && last.prediction && last.prediction.current_location) {
            const loc = last.prediction.current_location;
            latLng = [loc.lat, loc.lon];
        } 
        else if (last && last.prediction && last.prediction.finished) {
            const finishLabels = ['Finish', 'finish', '골인', '완주', '도착'];
            let finishPoint = null;
            for (const label of finishLabels) {
                if (splitPoints[label]) {
                    finishPoint = splitPoints[label];
                    break;
                }
            }
            if(finishPoint) {
                const coords = finishPoint;
                latLng = [coords[1], coords[0]];
            }
        } 
        else if (last && last.splits && last.splits.length) {
            const lastSplit = last.splits[last.splits.length - 1];
            const splitLabel = lastSplit.point_label;
            if (splitPoints[splitLabel]) {
                const coords = splitPoints[splitLabel];
                latLng = [coords[1], coords[0]];
            }
        }

        if (latLng) {
            if (runnerMarkers[p.id]) {
                runnerMarkers[p.id].setLatLng(latLng);
            } else {
                runnerMarkers[p.id] = L.marker(latLng, { icon: runnerIcon }).addTo(map);
                runnerMarkers[p.id].bindTooltip(p.alias || p.nameorbibno, { permanent: true, direction: 'top', offset: [-15, -42] });
            }
        }
    });

    for (const runnerId in runnerMarkers) {
        if (!activeRunners.has(parseInt(runnerId))) {
            runnerMarkers[runnerId].remove();
            delete runnerMarkers[runnerId];
        }
    }
}
