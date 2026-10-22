import * as L from '/static/vendor/leaflet/leaflet-src.esm.js';

export const BADGE_COLORS = {
  green: '#1e7b34',
  yellow: '#c99400',
  red: '#c0262d',
  grey: '#6b6b6b',
};

export function renderMiniMap(container, { lat, lng }, badgeColor) {
  const map = L.map(container, {
    center: [lat, lng],
    zoom: 19,
    scrollWheelZoom: false,
    dragging: !L.Browser.mobile,
    tap: false,
  });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap',
  }).addTo(map);
  L.circleMarker([lat, lng], {
    radius: 11,
    color: '#ffffff',
    weight: 3,
    fillColor: BADGE_COLORS[badgeColor] || BADGE_COLORS.grey,
    fillOpacity: 1,
  }).addTo(map);
  return map;
}
