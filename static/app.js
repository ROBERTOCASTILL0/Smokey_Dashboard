(() => {
  const raw = document.getElementById('snapshot-data');
  if (!raw || !window.L) return;
  let snapshot;
  try {
    snapshot = JSON.parse(raw.textContent || '{}');
  } catch (_err) {
    return;
  }
  const incidents = Array.isArray(snapshot.priority_incidents) ? snapshot.priority_incidents : [];
  const mapEl = document.getElementById('incident-map');
  if (!mapEl) return;

  const map = L.map(mapEl, { scrollWheelZoom: false });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  const coords = incidents
    .filter((item) => Number.isFinite(Number(item.latitude)) && Number.isFinite(Number(item.longitude)))
    .map((item) => [Number(item.latitude), Number(item.longitude)]);

  if (!coords.length) {
    map.setView([32.9, -116.9], 8);
    return;
  }

  const bounds = [];
  incidents.forEach((item) => {
    const lat = Number(item.latitude);
    const lng = Number(item.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    bounds.push([lat, lng]);
    const popup = `
      <strong>${item.name || 'Incident'}</strong><br>
      ${item.location || ''}<br>
      ${item.acreage || '0'} acres · ${item.containment || '0'}% contained
    `;
    L.marker([lat, lng]).addTo(map).bindPopup(popup);
  });

  map.fitBounds(bounds, { padding: [24, 24] });
})();
