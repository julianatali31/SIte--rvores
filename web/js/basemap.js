// Shared base map: satellite (Esri World Imagery) + OpenStreetMap, with a layer switcher.
import * as L from '/static/vendor/leaflet/leaflet-src.esm.js';

export { L };

export const BADGE_COLORS = {
  green: '#1e7b34',
  yellow: '#e0ad00',
  red: '#c0262d',
  grey: '#6b6b6b',
};

export const ZONE_STYLE = { color: '#ffd400', weight: 3, fillColor: '#ffd400', fillOpacity: 0.15 };

export function createBaseMap(container, { lat, lng }, zoom = 18, options = {}) {
  const satellite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 21, maxNativeZoom: 19, attribution: 'Imagens &copy; Esri' },
  );
  const streets = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 21, maxNativeZoom: 19, attribution: '&copy; OpenStreetMap',
  });
  const map = L.map(container, { center: [lat, lng], zoom, maxZoom: 21, layers: [satellite], ...options });
  L.control.layers({ 'Satélite': satellite, 'Mapa (OpenStreetMap)': streets }, null, { collapsed: false }).addTo(map);
  L.control.scale({ imperial: false }).addTo(map);
  return map;
}

export function treeMarker(lat, lng, color) {
  return L.circleMarker([lat, lng], {
    radius: 11, color: '#ffffff', weight: 3,
    fillColor: BADGE_COLORS[color] || BADGE_COLORS.grey, fillOpacity: 1,
  });
}
