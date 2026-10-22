import { api } from './api.js';
import { h } from './dom.js';
import { createBaseMap, L, treeMarker, ZONE_STYLE } from './basemap.js';

const listEl = document.getElementById('tree-list');
const summaryEl = document.getElementById('summary');

function card(p) {
  return h('div', { class: 'tree-card' },
    p.photo_url ? h('img', { src: p.photo_url, alt: '', loading: 'lazy' }) : null,
    h('p', { class: 'tree-card-title' }, `${p.common_name} · ${p.code}`),
    p.scientific_name
      ? h('p', { class: 'tree-card-sci' }, h('i', {}, p.scientific_name), p.species_reviewed ? '' : ' (nome em revisão)')
      : null,
    h('p', { class: `tree-card-badge badge-text-${p.badge_color}` },
      h('span', { class: `dot dot-${p.badge_color}` }), p.badge_headline,
      p.badge_detail ? ` (${p.badge_detail})` : ''),
    p.status === 'attention' ? h('p', { class: 'chip chip-warn' }, 'Em atenção') : null,
    h('a', { class: 'tree-card-link', href: p.url }, 'Ver árvore e registrar rega →'));
}

function summary(features) {
  if (!features.length) return 'Nenhuma árvore plantada ainda.';
  const needWater = features.filter((f) => f.properties.badge_color === 'red').length;
  const total = `${features.length} ${features.length === 1 ? 'árvore plantada' : 'árvores plantadas'}`;
  return needWater ? `${total} · ${needWater} precisando de água` : `${total} · todas em dia ou sem atraso`;
}

async function main() {
  const [config, trees, zones] = await Promise.all([
    api('/api/config'), api('/api/map/trees'), api('/api/map/zones'),
  ]);
  const map = createBaseMap(document.getElementById('map'), config.map_center, config.map_zoom, { tap: false });

  const bounds = L.latLngBounds([]);
  const zoneLayer = L.geoJSON(zones, {
    style: ZONE_STYLE,
    onEachFeature: (f, layer) => layer.bindTooltip(f.properties.name, { sticky: true }),
  }).addTo(map);
  if (zones.features.length) bounds.extend(zoneLayer.getBounds());

  const markers = new Map();
  // Open the card only after the map stops moving, so auto-pan keeps it clear of the controls.
  function focusTree(marker, zoom) {
    map.once('moveend', () => marker.openPopup());
    map.setView(marker.getLatLng(), zoom, { animate: false });
  }

  for (const feature of trees.features) {
    const [lng, lat] = feature.geometry.coordinates;
    const p = feature.properties;
    const marker = treeMarker(lat, lng, p.badge_color)
      .bindPopup(card(p), { maxWidth: 280, minWidth: 220, autoPanPaddingTopLeft: [60, 70], autoPanPaddingBottomRight: [20, 20] })
      .bindTooltip(p.code, { direction: 'top', offset: [0, -10] })
      .addTo(map);
    markers.set(p.public_id, marker);
    bounds.extend([lat, lng]);
  }
  if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 20 });

  summaryEl.textContent = summary(trees.features);
  listEl.replaceChildren(...trees.features.map(({ properties: p }) => {
    const show = h('button', { type: 'button', class: 'link-button' }, 'Ver no mapa');
    show.addEventListener('click', () => {
      const marker = markers.get(p.public_id);
      document.getElementById('map').scrollIntoView({ behavior: 'smooth' });
      focusTree(marker, Math.max(map.getZoom(), 20));
    });
    return h('li', {},
      h('span', { class: `dot dot-${p.badge_color}` }),
      h('a', { href: p.url }, h('strong', {}, p.code), ` ${p.common_name}`),
      h('span', { class: 'tree-list-badge' }, p.badge_headline),
      show);
  }));

  // /mapa#<public_id> (link from the tree page) opens that tree.
  const focus = markers.get(location.hash.slice(1));
  if (focus) focusTree(focus, 20);
}

main().catch(() => {
  summaryEl.textContent = 'Não foi possível carregar o mapa. Verifique a conexão e tente de novo.';
});
