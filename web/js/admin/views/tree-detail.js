import { h } from '../../dom.js';
import { createBaseMap, L, treeMarker, ZONE_STYLE } from '../../basemap.js';
import { adminApi, adminBlob, download } from '../http.js';
import { afterMount, getConfig } from '../config.js';
import { fitForUpload } from '../image.js';
import {
  badgeDot, busy, CARE_LABELS, emptyToNull, field, fmtDateTime, localInputValue,
  select, statusChip, STATUS_LABELS, toast,
} from '../ui.js';

const PLANTED = ['planted', 'attention'];

function reload() {
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

function editCard(tree, species, origins, zones) {
  const speciesSel = select('species_id', species.map((s) => [s.id, s.common_name]), tree.species_id);
  const originSel = select('origin_id', origins.map((o) => [o.id, o.donor_name]), tree.origin_id);
  const zoneSel = select('zone_id', zones.map((z) => [z.id, z.name]), tree.zone_id, { allowEmpty: true, emptyLabel: 'Sem zona' });
  const batch = h('input', { type: 'number', min: '1', value: tree.planting_batch ?? '' });
  const statusSel = select('status', Object.entries(STATUS_LABELS), tree.status);
  const notes = h('textarea', { rows: '3', maxlength: '4000' }, tree.notes ?? '');
  const save = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Salvar dados');
  const form = h('form', { class: 'card grid-form' },
    h('h2', {}, 'Dados da árvore'),
    field('Espécie', speciesSel), field('Origem', originSel), field('Zona', zoneSel),
    field('Lote', batch, 'Vazio = sem lote definido'),
    field('Status', statusSel, 'Para marcar como plantada use o quadro “Plantio” (precisa de data e local).'),
    field('Notas internas', notes), save);
  form.addEventListener('submit', busy(save, async () => {
    if (statusSel.value === 'awaiting_planting' && PLANTED.includes(tree.status)
        && !confirm('Voltar para “aguardando plantio” apaga a data de plantio. Continuar?')) return;
    await adminApi(`/api/admin/trees/${tree.id}`, {
      method: 'PATCH',
      json: {
        species_id: Number(speciesSel.value),
        origin_id: Number(originSel.value),
        zone_id: zoneSel.value ? Number(zoneSel.value) : null,
        planting_batch: batch.value ? Number(batch.value) : null,
        status: statusSel.value,
        notes: emptyToNull(notes.value),
      },
    });
    toast('Dados salvos.');
    reload();
  }));
  return form;
}

function plantCard(tree, zones, config) {
  const isPlanted = PLANTED.includes(tree.status);
  const when = h('input', { type: 'datetime-local', required: true,
    value: localInputValue(tree.planted_at ? new Date(tree.planted_at) : new Date()), max: localInputValue() });
  const lat = h('input', { type: 'number', step: 'any', inputmode: 'decimal', value: tree.lat ?? '', required: true });
  const lng = h('input', { type: 'number', step: 'any', inputmode: 'decimal', value: tree.lng ?? '', required: true });
  const zoneSel = select('zone_id', zones.map((z) => [z.id, z.name]), tree.zone_id, { allowEmpty: true, emptyLabel: 'Sem zona' });
  const gpsInfo = h('p', { class: 'muted small' });
  const mapBox = h('div', { class: 'admin-map' });
  const gpsBtn = h('button', { type: 'button', class: 'btn' }, '📍 Usar minha posição');
  const save = h('button', { type: 'submit', class: 'btn btn-primary' }, isPlanted ? 'Salvar plantio' : '🌱 Marcar como plantada');

  let marker = null;
  let map = null;
  function setPoint(la, ln, pan = false) {
    lat.value = la.toFixed(7);
    lng.value = ln.toFixed(7);
    if (!map) return;
    if (marker) marker.setLatLng([la, ln]);
    else marker = treeMarker(la, ln, tree.badge_color || 'grey').addTo(map);
    if (pan) map.setView([la, ln], Math.max(map.getZoom(), 19));
  }

  afterMount(() => {
    const center = tree.lat != null ? { lat: tree.lat, lng: tree.lng } : config.map_center;
    map = createBaseMap(mapBox, center, tree.lat != null ? 20 : config.map_zoom);
    for (const zone of zones) {
      if (zone.polygon_geojson) L.geoJSON(zone.polygon_geojson, { style: ZONE_STYLE, interactive: false }).addTo(map);
    }
    if (tree.lat != null) setPoint(tree.lat, tree.lng);
    map.on('click', (e) => setPoint(e.latlng.lat, e.latlng.lng));
  });

  gpsBtn.addEventListener('click', () => {
    if (!navigator.geolocation) { toast('Este aparelho não informa a localização.', 'error'); return; }
    gpsInfo.textContent = 'Obtendo localização…';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPoint(pos.coords.latitude, pos.coords.longitude, true);
        const acc = Math.round(pos.coords.accuracy);
        gpsInfo.textContent = `Precisão aproximada: ${acc} m.${acc > 15 ? ' Ajuste tocando no mapa, se precisar.' : ''}`;
      },
      (err) => {
        gpsInfo.textContent = '';
        toast(err.code === 1 ? 'Permissão de localização negada.' : 'Não foi possível obter a localização (o site precisa estar em HTTPS).', 'error');
      },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
    );
  });

  const form = h('form', { class: 'card' },
    h('h2', {}, isPlanted ? 'Plantio e localização' : 'Plantio'),
    h('p', { class: 'muted small' }, 'Toque no mapa para marcar o local exato, ou use a posição do celular ao lado da muda.'),
    mapBox,
    h('div', { class: 'row' }, gpsBtn, gpsInfo),
    h('div', { class: 'grid-form' },
      field('Data e hora do plantio', when), field('Latitude', lat), field('Longitude', lng), field('Zona', zoneSel)),
    save);
  form.addEventListener('submit', busy(save, async () => {
    if (!lat.value || !lng.value) throw new Error('Marque o local no mapa.');
    await adminApi(`/api/admin/trees/${tree.id}/plant`, {
      method: 'POST',
      json: {
        planted_at: when.value,
        lat: Number(lat.value),
        lng: Number(lng.value),
        zone_id: zoneSel.value ? Number(zoneSel.value) : null,
      },
    });
    toast(isPlanted ? 'Plantio atualizado.' : `${tree.code} marcada como plantada!`);
    reload();
  }));
  return form;
}

async function photosCard(tree) {
  const photos = await adminApi(`/api/admin/trees/${tree.id}/photos`);
  const fileInput = h('input', { type: 'file', accept: 'image/jpeg,image/png,image/webp', required: true });
  const caption = h('input', { type: 'text', maxlength: '200', placeholder: 'Ex.: dia do plantio' });
  const when = h('input', { type: 'datetime-local', max: localInputValue() });
  const send = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Enviar foto');
  const form = h('form', { class: 'grid-form' },
    field('Foto', fileInput), field('Legenda', caption),
    field('Data da foto', when, 'Vazio = data da câmera (EXIF) ou agora'), send);
  form.addEventListener('submit', busy(send, async () => {
    if (!fileInput.files[0]) throw new Error('Escolha uma foto.');
    const config = await getConfig();
    const data = new FormData();
    // Reduced photos lose the camera date: fill "Data da foto" if it matters.
    data.append('file', await fitForUpload(fileInput.files[0], config.max_upload_mb));
    if (caption.value.trim()) data.append('caption', caption.value.trim());
    if (when.value) data.append('taken_at', when.value);
    await adminApi(`/api/admin/trees/${tree.id}/photos`, { method: 'POST', form: data });
    toast('Foto enviada. Localização e dados da câmera foram removidos.');
    reload();
  }));

  const list = h('ul', { class: 'photo-grid' }, photos.map((p) => {
    const del = h('button', { type: 'button', class: 'btn btn-danger btn-small' }, 'Excluir');
    del.addEventListener('click', busy(del, async () => {
      if (!confirm('Excluir esta foto?')) return;
      await adminApi(`/api/admin/trees/${tree.id}/photos/${p.id}`, { method: 'DELETE' });
      reload();
    }));
    return h('li', {}, h('img', { src: p.url, alt: p.caption || 'Foto', loading: 'lazy' }),
      h('span', {}, fmtDateTime(p.taken_at)), p.caption ? h('span', { class: 'muted' }, p.caption) : null, del);
  }));
  return h('section', { class: 'card' }, h('h2', {}, 'Fotos'),
    photos.length ? list : h('p', { class: 'muted' }, 'Nenhuma foto ainda.'), form);
}

async function careCard(tree) {
  const events = await adminApi(`/api/admin/trees/${tree.id}/care-events`);
  const typeSel = select('type', Object.entries(CARE_LABELS), 'fertilizing');
  const when = h('input', { type: 'datetime-local', value: localInputValue(), max: localInputValue() });
  const who = h('input', { type: 'text', maxlength: '60' });
  const notes = h('input', { type: 'text', maxlength: '280' });
  const add = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Registrar cuidado');
  const form = h('form', { class: 'grid-form' },
    field('Tipo', typeSel), field('Quando', when), field('Quem', who), field('Observação', notes), add);
  form.addEventListener('submit', busy(add, async () => {
    await adminApi(`/api/admin/trees/${tree.id}/care-events`, {
      method: 'POST',
      json: { type: typeSel.value, performed_at: when.value || null, performed_by_name: emptyToNull(who.value), notes: emptyToNull(notes.value) },
    });
    toast('Cuidado registrado.');
    reload();
  }));

  const rows = events.map((e) => {
    const del = h('button', { type: 'button', class: 'btn btn-danger btn-small' }, 'Excluir');
    del.addEventListener('click', busy(del, async () => {
      if (!confirm('Excluir este registro? (use para remover registros falsos)')) return;
      await adminApi(`/api/admin/trees/${tree.id}/care-events/${e.id}`, { method: 'DELETE' });
      reload();
    }));
    return h('tr', {},
      h('td', {}, CARE_LABELS[e.type]), h('td', {}, fmtDateTime(e.performed_at)),
      h('td', {}, e.performed_by_name || '—'), h('td', {}, e.source === 'public' ? 'QR público' : 'Admin'),
      h('td', {}, e.notes || ''), h('td', {}, del));
  });
  return h('section', { class: 'card' }, h('h2', {}, 'Cuidados (regas, adubação, poda)'),
    events.length
      ? h('div', { class: 'table-wrap' }, h('table', {},
          h('thead', {}, h('tr', {}, ['Tipo', 'Quando', 'Quem', 'Origem', 'Obs.', ''].map((c) => h('th', {}, c)))),
          h('tbody', {}, rows)))
      : h('p', { class: 'muted' }, 'Nenhum registro.'),
    form);
}

function qrCard(tree) {
  if (!PLANTED.includes(tree.status)) {
    return h('section', { class: 'card' }, h('h2', {}, 'QR Code'),
      h('p', { class: 'muted' }, 'O QR fica disponível depois que a árvore for marcada como plantada.'));
  }
  const img = h('img', { class: 'qr-preview', alt: `QR Code de ${tree.code}` });
  adminBlob(`/api/admin/trees/${tree.id}/qr.png`).then((blob) => { img.src = URL.createObjectURL(blob); }).catch(() => {});
  const png = h('button', { type: 'button', class: 'btn' }, 'Baixar PNG');
  const svg = h('button', { type: 'button', class: 'btn' }, 'Baixar SVG');
  png.addEventListener('click', busy(png, () => download(`/api/admin/trees/${tree.id}/qr.png`, `${tree.code}-qr.png`)));
  svg.addEventListener('click', busy(svg, () => download(`/api/admin/trees/${tree.id}/qr.svg`, `${tree.code}-qr.svg`)));
  return h('section', { class: 'card' }, h('h2', {}, 'QR Code'), img,
    h('p', { class: 'small' }, 'Aponta para ', h('code', {}, tree.public_url)),
    h('div', { class: 'row' }, png, svg));
}

export async function treeDetail(id) {
  const [tree, species, origins, zones, config] = await Promise.all([
    adminApi(`/api/admin/trees/${id}`),
    adminApi('/api/admin/species'),
    adminApi('/api/admin/origins'),
    adminApi('/api/admin/zones'),
    getConfig(),
  ]);
  const deleteBtn = h('button', { type: 'button', class: 'btn btn-danger' }, 'Excluir muda');
  deleteBtn.addEventListener('click', busy(deleteBtn, async () => {
    if (!confirm(`Excluir ${tree.code}? Isso não pode ser desfeito.`)) return;
    await adminApi(`/api/admin/trees/${tree.id}`, { method: 'DELETE' });
    toast(`${tree.code} excluída.`);
    location.hash = '#/arvores';
  }));

  return [
    h('p', {}, h('a', { href: '#/arvores' }, '← Árvores')),
    h('div', { class: 'page-head' },
      h('h1', {}, `${tree.code} · ${tree.species_name}`),
      h('div', { class: 'row' }, statusChip(tree.status), badgeDot(tree.badge_color, tree.badge_headline),
        h('a', { href: `/a/${tree.public_id}`, target: '_blank', rel: 'noopener' }, 'Ver página pública ↗'))),
    plantCard(tree, zones, config),
    editCard(tree, species, origins, zones),
    await photosCard(tree),
    PLANTED.includes(tree.status) ? await careCard(tree) : null,
    qrCard(tree),
    tree.status === 'awaiting_planting' ? h('section', { class: 'card' }, deleteBtn) : null,
  ].filter(Boolean);
}
