import { h } from '../../dom.js';
import { adminApi } from '../http.js';
import { badgeDot, busy, field, select, statusChip, STATUS_LABELS, toast } from '../ui.js';

export async function treeList() {
  const [trees, species, origins, zones] = await Promise.all([
    adminApi('/api/admin/trees'),
    adminApi('/api/admin/species'),
    adminApi('/api/admin/origins'),
    adminApi('/api/admin/zones'),
  ]);

  const counts = Object.fromEntries(Object.keys(STATUS_LABELS).map((s) => [s, trees.filter((t) => t.status === s).length]));
  const filter = select('status', Object.entries(STATUS_LABELS).map(([k, v]) => [k, `${v} (${counts[k]})`]), '',
    { allowEmpty: true, emptyLabel: `Todas (${trees.length})` });
  const tbody = h('tbody');

  function renderRows() {
    const rows = trees.filter((t) => !filter.value || t.status === filter.value);
    tbody.replaceChildren(...rows.map((t) => h('tr', {},
      h('td', {}, h('a', { href: `#/arvores/${t.id}` }, t.code)),
      h('td', {}, t.species_name),
      h('td', {}, statusChip(t.status)),
      h('td', {}, t.planting_batch ?? '—'),
      h('td', {}, t.zone_name ?? '—'),
      h('td', {}, badgeDot(t.badge_color, t.badge_headline)),
    )));
  }
  filter.addEventListener('change', renderRows);
  renderRows();

  const speciesSel = select('species_id', species.map((s) => [s.id, s.common_name]), species[0]?.id);
  const originSel = select('origin_id', origins.map((o) => [o.id, o.donor_name]), origins[0]?.id);
  const zoneSel = select('zone_id', zones.map((z) => [z.id, z.name]), '', { allowEmpty: true, emptyLabel: 'Sem zona' });
  const batch = h('input', { name: 'planting_batch', type: 'number', min: '1', inputmode: 'numeric' });
  const createBtn = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Cadastrar muda');
  const form = h('form', { class: 'card grid-form' },
    h('h2', {}, 'Nova muda'),
    field('Espécie', speciesSel), field('Origem', originSel), field('Zona', zoneSel),
    field('Lote', batch, 'Vazio = sem lote definido'), createBtn);
  form.addEventListener('submit', busy(createBtn, async () => {
    const tree = await adminApi('/api/admin/trees', {
      method: 'POST',
      json: {
        species_id: Number(speciesSel.value),
        origin_id: Number(originSel.value),
        zone_id: zoneSel.value ? Number(zoneSel.value) : null,
        planting_batch: batch.value ? Number(batch.value) : null,
      },
    });
    toast(`${tree.code} cadastrada.`);
    location.hash = `#/arvores/${tree.id}`;
  }));

  return [
    h('div', { class: 'page-head' }, h('h1', {}, 'Árvores'), field('Filtrar por status', filter)),
    h('div', { class: 'card table-wrap' },
      h('table', {},
        h('thead', {}, h('tr', {}, ['Código', 'Espécie', 'Status', 'Lote', 'Zona', 'Rega'].map((c) => h('th', {}, c)))),
        tbody)),
    form,
  ];
}
