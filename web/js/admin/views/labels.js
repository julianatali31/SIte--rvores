import { h } from '../../dom.js';
import { adminApi, download } from '../http.js';
import { getConfig } from '../config.js';
import { busy, statusChip } from '../ui.js';

export async function labelsView() {
  const [trees, config] = await Promise.all([adminApi('/api/admin/trees'), getConfig()]);
  const planted = trees.filter((t) => ['planted', 'attention'].includes(t.status));
  const local = /localhost|127\.0\.0\.1|\.local\b/.test(config.base_url);

  const boxes = planted.map((t) => ({ tree: t, input: h('input', { type: 'checkbox', checked: true, value: String(t.id) }) }));
  const allBtn = h('button', { type: 'button', class: 'btn btn-primary btn-big' }, '📄 Gerar PDF A4 das etiquetas');
  allBtn.addEventListener('click', busy(allBtn, async () => {
    const ids = boxes.filter((b) => b.input.checked).map((b) => `ids=${b.input.value}`);
    if (!ids.length) throw new Error('Selecione pelo menos uma árvore.');
    await download(`/api/admin/labels.pdf?${ids.join('&')}`, 'etiquetas-arvores.pdf');
  }));

  return [
    h('h1', {}, 'QR Codes e etiquetas'),
    h('section', { class: `card ${local ? 'card-danger' : ''}` },
      h('h2', {}, 'Endereço impresso nos QR Codes'),
      h('p', {}, h('code', { class: 'big-code' }, `${config.base_url}/a/…`)),
      local
        ? h('p', { class: 'notice notice-danger' }, '⛔ Este endereço é local. NÃO imprima placas com ele: configure BASE_URL com o domínio definitivo.')
        : h('p', { class: 'notice notice-warn' }, '⚠️ Depois de imprimir, este endereço não pode mudar. Confirme que o domínio é definitivo.')),
    h('section', { class: 'card' },
      h('h2', {}, `Árvores plantadas (${planted.length})`),
      planted.length
        ? h('ul', { class: 'check-list' }, boxes.map(({ tree, input }) => h('li', {},
            h('label', { class: 'check' }, input, ` ${tree.code} · ${tree.species_name} `, statusChip(tree.status)),
            h('a', { href: `#/arvores/${tree.id}` }, 'QR individual'))))
        : h('p', { class: 'muted' }, 'Nenhuma árvore plantada ainda. Marque o plantio na página de cada árvore.'),
      planted.length ? allBtn : null,
      h('p', { class: 'muted small' }, '6 etiquetas por folha A4 (QR + código + nome). O QR usa correção de erro nível H.')),
  ];
}
