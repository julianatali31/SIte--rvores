import { h } from '../../dom.js';
import { adminApi } from '../http.js';
import { busy, emptyToNull, field, select, toast } from '../ui.js';

const REVIEW = [['pending', 'Pendente (mostra “em revisão”)'], ['reviewed', 'Revisado']];

export async function speciesList() {
  const species = await adminApi('/api/admin/species');
  return [
    h('div', { class: 'page-head' }, h('h1', {}, 'Espécies'), h('a', { class: 'btn btn-primary', href: '#/especies/nova' }, '+ Nova espécie')),
    h('div', { class: 'card table-wrap' }, h('table', {},
      h('thead', {}, h('tr', {}, ['Nome popular', 'Nome científico', 'Revisão', 'Árvores'].map((c) => h('th', {}, c)))),
      h('tbody', {}, species.map((s) => h('tr', {},
        h('td', {}, h('a', { href: `#/especies/${s.id}` }, s.common_name)),
        h('td', {}, s.scientific_name ? h('i', {}, s.scientific_name) : h('span', { class: 'muted' }, '—')),
        h('td', {}, s.data_review_status === 'reviewed' ? '✓ Revisado' : h('span', { class: 'chip chip-warn' }, 'Pendente')),
        h('td', {}, String(s.tree_count))))))),
  ];
}

export async function speciesForm(id) {
  const sp = id ? await adminApi(`/api/admin/species/${id}`) : {};
  const input = (name, max) => h('input', { name, type: 'text', maxlength: String(max), value: sp[name] ?? '' });
  const area = (name, max) => h('textarea', { name, rows: '3', maxlength: String(max) }, sp[name] ?? '');
  const fields = {
    common_name: input('common_name', 120),
    scientific_name: input('scientific_name', 160),
    size_class: input('size_class', 60),
    fruiting_season: input('fruiting_season', 120),
    description: area('description', 4000),
    root_notes: area('root_notes', 2000),
    fun_fact: area('fun_fact', 2000),
  };
  fields.common_name.required = true;
  const review = select('data_review_status', REVIEW, sp.data_review_status || 'pending');
  const save = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Salvar');
  const form = h('form', { class: 'card grid-form' },
    h('p', { class: 'notice wide' }, 'Preencha só com informação confirmada. Campo vazio aparece como “informação em revisão” na página pública. O nome científico só sai nas etiquetas quando a espécie estiver “Revisado”.'),
    field('Nome popular', fields.common_name),
    field('Nome científico', fields.scientific_name),
    field('Porte', fields.size_class),
    field('Época de frutos', fields.fruiting_season),
    field('Descrição', fields.description),
    field('Observações sobre a raiz', fields.root_notes),
    field('Curiosidade', fields.fun_fact),
    field('Status da revisão', review),
    save);
  form.addEventListener('submit', busy(save, async () => {
    const json = Object.fromEntries(Object.entries(fields).map(([k, el]) => [k, emptyToNull(el.value)]));
    json.data_review_status = review.value;
    const saved = await adminApi(id ? `/api/admin/species/${id}` : '/api/admin/species', { method: id ? 'PATCH' : 'POST', json });
    toast('Espécie salva.');
    location.hash = `#/especies/${saved.id}`;
    if (id) window.dispatchEvent(new HashChangeEvent('hashchange'));
  }));

  const content = [
    h('p', {}, h('a', { href: '#/especies' }, '← Espécies')),
    h('h1', {}, id ? sp.common_name : 'Nova espécie'),
    form,
  ];

  if (id) {
    const file = h('input', { type: 'file', accept: 'image/jpeg,image/png,image/webp' });
    const send = h('button', { type: 'submit', class: 'btn' }, 'Enviar foto da espécie');
    const photoForm = h('form', { class: 'card' }, h('h2', {}, 'Foto da espécie'),
      sp.photo_path ? h('img', { class: 'species-photo', src: `/media/${sp.photo_path}`, alt: sp.common_name }) : h('p', { class: 'muted' }, 'Sem foto. A página usa a foto mais recente da árvore, se houver.'),
      field('Arquivo', file), send);
    photoForm.addEventListener('submit', busy(send, async () => {
      if (!file.files[0]) throw new Error('Escolha uma imagem.');
      const data = new FormData();
      data.append('file', file.files[0]);
      await adminApi(`/api/admin/species/${id}/photo`, { method: 'POST', form: data });
      toast('Foto enviada.');
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    }));
    content.push(photoForm);

    if (sp.tree_count === 0) {
      const del = h('button', { type: 'button', class: 'btn btn-danger' }, 'Excluir espécie');
      del.addEventListener('click', busy(del, async () => {
        if (!confirm(`Excluir ${sp.common_name}?`)) return;
        await adminApi(`/api/admin/species/${id}`, { method: 'DELETE' });
        location.hash = '#/especies';
      }));
      content.push(h('section', { class: 'card' }, del));
    }
  }
  return content;
}
