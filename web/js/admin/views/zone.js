import { h } from '../../dom.js';
import { createBaseMap, L, treeMarker, ZONE_STYLE } from '../../basemap.js';
import { adminApi } from '../http.js';
import { afterMount, getConfig } from '../config.js';
import { busy, emptyToNull, field, toast } from '../ui.js';
import { PolygonEditor } from '../polygon-editor.js';

function zoneCard(zone, trees, config) {
  const mapBox = h('div', { class: 'admin-map admin-map-tall' });
  const status = h('p', { class: 'small' });
  const drawBtn = h('button', { type: 'button', class: 'btn' }, '✏️ Adicionar pontos');
  const undoBtn = h('button', { type: 'button', class: 'btn' }, '↶ Desfazer ponto');
  const clearBtn = h('button', { type: 'button', class: 'btn' }, 'Limpar desenho');
  const saveBtn = h('button', { type: 'button', class: 'btn btn-primary' }, 'Salvar polígono');
  const removeBtn = h('button', { type: 'button', class: 'btn btn-danger' }, 'Remover polígono salvo');
  const fileInput = h('input', { type: 'file', accept: '.geojson,.json,application/geo+json,application/json' });
  const importBtn = h('button', { type: 'button', class: 'btn' }, 'Importar GeoJSON');
  let editor = null;
  let multiLayer = null;

  function updateStatus() {
    const n = editor?.points.length ?? 0;
    status.textContent = editor?.drawing
      ? `Modo desenho: toque no mapa para adicionar pontos (${n}). Arraste um ponto para mover; toque nele para remover.`
      : n ? `${n} pontos. Arraste para ajustar.` : 'Sem polígono. Use “Adicionar pontos” ou importe um GeoJSON.';
    saveBtn.disabled = n > 0 && n < 3;
  }

  afterMount(() => {
    const map = createBaseMap(mapBox, config.map_center, config.map_zoom);
    for (const t of trees) {
      if (t.lat != null) treeMarker(t.lat, t.lng, t.badge_color).bindTooltip(t.code).addTo(map);
    }
    editor = new PolygonEditor(map, updateStatus);
    if (zone.polygon_geojson?.type === 'MultiPolygon') {
      multiLayer = L.geoJSON(zone.polygon_geojson, { style: ZONE_STYLE }).addTo(map);
      map.fitBounds(multiLayer.getBounds(), { padding: [30, 30] });
      toast('Zona com vários polígonos (importada). Para editar, limpe e desenhe de novo.', 'info');
    } else {
      editor.load(zone.polygon_geojson);
      editor.fit();
    }
    updateStatus();
  });

  drawBtn.addEventListener('click', () => {
    editor.setDrawing(!editor.drawing);
    drawBtn.textContent = editor.drawing ? '✋ Parar de adicionar' : '✏️ Adicionar pontos';
    updateStatus();
  });
  undoBtn.addEventListener('click', () => editor.undo());
  clearBtn.addEventListener('click', () => {
    editor.clear();
    multiLayer?.remove();
    multiLayer = null;
  });
  saveBtn.addEventListener('click', busy(saveBtn, async () => {
    const geometry = editor.toGeoJSON();
    if (!geometry && multiLayer) throw new Error('Nada novo para salvar.');
    if (!geometry) throw new Error('Desenhe pelo menos 3 pontos.');
    await adminApi(`/api/admin/zones/${zone.id}`, { method: 'PATCH', json: { polygon_geojson: geometry } });
    editor.setDrawing(false);
    drawBtn.textContent = '✏️ Adicionar pontos';
    updateStatus();
    toast('Polígono salvo.');
  }));
  removeBtn.addEventListener('click', busy(removeBtn, async () => {
    if (!confirm('Remover o polígono salvo desta zona?')) return;
    await adminApi(`/api/admin/zones/${zone.id}`, { method: 'PATCH', json: { polygon_geojson: null } });
    toast('Polígono removido.');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }));
  importBtn.addEventListener('click', busy(importBtn, async () => {
    const file = fileInput.files[0];
    if (!file) throw new Error('Escolha um arquivo .geojson.');
    if (file.size > 2 * 1024 * 1024) throw new Error('Arquivo grande demais (máx. 2 MB).');
    let data;
    try { data = JSON.parse(await file.text()); } catch { throw new Error('O arquivo não é um JSON válido.'); }
    await adminApi(`/api/admin/zones/${zone.id}/geojson`, { method: 'PUT', json: data });
    toast('GeoJSON importado.');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }));

  const description = h('textarea', { rows: '3', maxlength: '4000' }, zone.description ?? '');
  const restrictions = h('textarea', { rows: '4', maxlength: '4000' }, zone.restrictions ?? '');
  const saveText = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Salvar textos');
  const textForm = h('form', { class: 'grid-form' },
    field('Descrição', description), field('Restrições', restrictions), saveText);
  textForm.addEventListener('submit', busy(saveText, async () => {
    await adminApi(`/api/admin/zones/${zone.id}`, {
      method: 'PATCH', json: { description: emptyToNull(description.value), restrictions: emptyToNull(restrictions.value) },
    });
    toast('Textos salvos.');
  }));

  return h('section', { class: 'card' },
    h('h2', {}, zone.name),
    mapBox, status,
    h('div', { class: 'row' }, drawBtn, undoBtn, clearBtn, saveBtn),
    h('div', { class: 'row' }, field('Arquivo GeoJSON (Polygon/MultiPolygon, Feature ou FeatureCollection com 1 polígono)', fileInput), importBtn),
    zone.polygon_geojson ? h('div', { class: 'row' }, removeBtn) : null,
    textForm);
}

export async function zoneView() {
  const [zones, trees, config] = await Promise.all([
    adminApi('/api/admin/zones'), adminApi('/api/admin/trees'), getConfig(),
  ]);
  return [h('h1', {}, 'Zonas de plantio'), ...zones.map((z) => zoneCard(z, trees, config))];
}
