document.addEventListener('DOMContentLoaded', () => {
    const marathonId = window.MARATHON_ID;
    if (marathonId) {
        initFullMap(marathonId);
    }
});

let map = null;
let splitPoints = {};
let runnerMarkers = {};
let participants = [];
let marathonData = null;

const REFRESH_INTERVAL = 20000; // 20 seconds

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

async function initFullMap(marathonId) {
    try {
        // 1. Fetch marathon data (for name and course)
        marathonData = await api(`/api/marathons/${marathonId}/map_data`);
        document.getElementById('marathon-name').textContent = marathonData.name;

        // 2. Initialize map
        map = L.map('map');
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        // 3. Draw course and split points
        if (marathonData.course_geo_json) {
            const geoJsonFeature = marathonData.course_geo_json;
            const geoJsonLayer = L.geoJSON(geoJsonFeature).addTo(map);
            map.fitBounds(geoJsonLayer.getBounds());

            if (geoJsonFeature.properties && geoJsonFeature.properties.split_points) {
                splitPoints = geoJsonFeature.properties.split_points;
                renderSplitPointMarkers();
            }
        }

        // 4. Initial data load and setup refresh
        await refreshAllParticipantData(marathonId);
        setInterval(() => refreshAllParticipantData(marathonId), REFRESH_INTERVAL);

    } catch (error) {
        document.getElementById('marathon-name').textContent = '데이터 로드 실패';
        console.error('Map initialization failed:', error);
    }
}

async function refreshAllParticipantData(marathonId) {
    try {
        // 1. Get all participants for the marathon
        participants = await api(`/api/marathons/${marathonId}/participants`);

        // 2. Fetch detailed data for each
        const promises = participants.map(p =>
            api(`/api/participant_data?participant_id=${p.id}`).then(data => {
                p._last = data;
            }).catch(() => {
                p._last = { msg: '로드 오류' };
            })
        );
        await Promise.all(promises);

        // 3. Update markers
        updateRunnerMarkers();
        
        document.getElementById('last-updated').textContent = `마지막 업데이트: ${new Date().toLocaleTimeString()}`;

    } catch (error) {
        console.error('Failed to refresh participant data:', error);
    }
}

function renderSplitPointMarkers() {
    if (!map) return;
    for (const label in splitPoints) {
        const coords = splitPoints[label];
        L.marker([coords[1], coords[0]], {
            icon: L.divIcon({
                className: 'split-point-icon', // You might want to style this differently
                html: `<div>${label}</div>`,
                iconSize: [40, 20]
            })
        }).addTo(map);
    }
}

function updateRunnerMarkers() {
    if (!map || !Object.keys(splitPoints).length) return;

    const activeRunners = new Set();

    participants.forEach(p => {
        activeRunners.add(p.id);
        const last = p._last;
        let latLng = null;

        // Logic for finished runners
        if (last && last.prediction && last.prediction.finished) {
            if (splitPoints['Finish']) {
                const coords = splitPoints['Finish'];
                latLng = [coords[1], coords[0]];
            }
        } 
        // Logic for runners in progress
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
                runnerMarkers[p.id] = L.marker(latLng, {
                    icon: L.divIcon({
                        className: 'runner-icon',
                        html: `<div>${p.alias || p.nameorbibno}</div>`,
                        iconSize: [60, 20]
                    })
                }).addTo(map);
            }
            const popupText = `<b>${p.alias || p.nameorbibno}</b><br>${(last.splits && last.splits.length) ? last.splits[last.splits.length - 1].point_label : '대기중'}`;
            runnerMarkers[p.id].bindPopup(popupText);
        }
    });

    // Remove markers for inactive runners
    for (const runnerId in runnerMarkers) {
        if (!activeRunners.has(parseInt(runnerId))) {
            runnerMarkers[runnerId].remove();
            delete runnerMarkers[runnerId];
        }
    }
}
