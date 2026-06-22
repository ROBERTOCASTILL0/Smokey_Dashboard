(() => {
  'use strict';

  // ---- Snapshot ----------------------------------------------------------
  let snapshot = {};
  try {
    const raw = document.getElementById('snapshot-data');
    snapshot = raw ? JSON.parse(raw.textContent || '{}') : {};
  } catch (_err) {
    snapshot = {};
  }
  const incidents = Array.isArray(snapshot.priority_incidents) ? snapshot.priority_incidents : [];
  const config = snapshot.dashboard_config || {};
  const mapCenter = Array.isArray(config.defaultMapCenter) ? config.defaultMapCenter : [32.95, -116.85];
  const mapZoom = Number.isFinite(config.defaultMapZoom) ? config.defaultMapZoom : 8;

  // ---- Tab navigation ----------------------------------------------------
  const tabBtns = Array.from(document.querySelectorAll('.tab-btn'));
  const panels = Array.from(document.querySelectorAll('[data-tab-panel]'));
  const onTabShow = {};

  function activateTab(name) {
    let matched = false;
    tabBtns.forEach((btn) => {
      const active = btn.dataset.tab === name;
      btn.classList.toggle('is-active', active);
      if (active) matched = true;
    });
    if (!matched) return;
    panels.forEach((p) => p.classList.toggle('is-active', p.dataset.tabPanel === name));
    if (typeof onTabShow[name] === 'function') onTabShow[name]();
    if (window.scrollY > 0) window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  tabBtns.forEach((btn) => btn.addEventListener('click', () => activateTab(btn.dataset.tab)));

  // "View all" / cross-section jump buttons
  document.querySelectorAll('[data-goto]').forEach((el) => {
    el.addEventListener('click', () => {
      activateTab(el.dataset.goto);
      closeDrawer();
    });
  });

  // ---- Source health drawer ---------------------------------------------
  const overlay = document.getElementById('drawer-overlay');
  const drawer = document.getElementById('source-drawer');
  const pill = document.getElementById('source-pill');
  const closeBtn = document.getElementById('drawer-close');

  function openDrawer() {
    if (!drawer) return;
    drawer.classList.add('is-open');
    overlay.classList.add('is-open');
  }
  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove('is-open');
    overlay.classList.remove('is-open');
  }
  if (pill) pill.addEventListener('click', openDrawer);
  if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
  if (overlay) overlay.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });

  // ---- Maps --------------------------------------------------------------
  if (!window.L) return;

  const geoIncidents = incidents.filter(
    (i) => Number.isFinite(Number(i.latitude)) && Number.isFinite(Number(i.longitude))
  );

  function statusColor(status) {
    return (status || '').toUpperCase() === 'ACTIVE' ? '#E5484D' : '#22C55E';
  }

  function incidentPopup(i) {
    const acres = i.acreage != null ? i.acreage : '0';
    const cont = i.containment != null ? i.containment : '0';
    return (
      '<strong>' + (i.name || 'Incident') + '</strong><br>' +
      (i.location || '') + '<br>' +
      acres + ' acres &middot; ' + cont + '% contained'
    );
  }

  function buildMap(elId, opts) {
    const el = document.getElementById(elId);
    if (!el) return null;
    const map = L.map(el, { scrollWheelZoom: false, zoomControl: opts.zoomControl !== false });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const incidentLayer = L.layerGroup();
    const bounds = [];
    geoIncidents.forEach((i) => {
      const lat = Number(i.latitude);
      const lng = Number(i.longitude);
      bounds.push([lat, lng]);
      L.circleMarker([lat, lng], {
        radius: 9,
        color: statusColor(i.incident_status),
        fillColor: statusColor(i.incident_status),
        fillOpacity: 0.55,
        weight: 2
      }).addTo(incidentLayer).bindPopup(incidentPopup(i));
    });
    incidentLayer.addTo(map);

    // Watch areas layer (from dashboard_config.watchAreas) — off by default
    const watchLayer = L.layerGroup();
    (config.watchAreas || []).forEach((w) => {
      if (!Array.isArray(w.center)) return;
      const radiusM = (Number(w.radiusMiles) || 0) * 1609.34;
      L.circle(w.center, {
        radius: radiusM,
        color: '#38BDF8',
        weight: 1,
        fillColor: '#38BDF8',
        fillOpacity: 0.06
      }).addTo(watchLayer).bindTooltip(w.name || 'Watch area');
    });

    if (bounds.length) {
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 11 });
    } else {
      map.setView(mapCenter, mapZoom);
    }
    return { map: map, layers: { incidents: incidentLayer, watch: watchLayer } };
  }

  // Mini map (overview) — initialized now since overview is visible by default.
  const mini = buildMap('mini-map', { zoomControl: false });

  // Full map (Map tab) — initialized lazily on first show so Leaflet sizes correctly.
  let full = null;
  onTabShow.map = function () {
    if (!full) {
      full = buildMap('full-map', { zoomControl: true });
      wireLayerToggles();
    }
    if (full) setTimeout(() => full.map.invalidateSize(), 60);
  };
  if (mini) {
    // overview already visible; ensure correct sizing after layout settles
    setTimeout(() => mini.map.invalidateSize(), 60);
  }

  function wireLayerToggles() {
    document.querySelectorAll('.layer-toggle[data-layer]').forEach((btn) => {
      if (btn.disabled) return;
      btn.addEventListener('click', () => {
        const key = btn.dataset.layer;
        const layer = full && full.layers[key];
        if (!layer) return;
        const pressed = btn.getAttribute('aria-pressed') === 'true';
        if (pressed) {
          full.map.removeLayer(layer);
          btn.setAttribute('aria-pressed', 'false');
        } else {
          layer.addTo(full.map);
          btn.setAttribute('aria-pressed', 'true');
        }
      });
    });
  }
})();
