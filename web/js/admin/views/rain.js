import { h } from '../../dom.js';
import { adminApi } from '../http.js';
import { busy, emptyToNull, field, fmtDateTime, localInputValue, toast } from '../ui.js';

const PHASES = { newly_planted: 'Recém-plantada', established: 'Estabelecida' };

function reload() {
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

function rainCard(events) {
  const when = h('input', { type: 'datetime-local', value: localInputValue(), max: localInputValue() });
  const mm = h('input', { type: 'number', min: '0', max: '1000', step: '0.1', inputmode: 'decimal', placeholder: 'opcional' });
  const notes = h('input', { type: 'text', maxlength: '280', placeholder: 'Ex.: chuva forte à tarde' });
  const add = h('button', { type: 'submit', class: 'btn btn-primary btn-big' }, '🌧️ Choveu');
  const form = h('form', { class: 'grid-form' },
    field('Quando', when), field('Milímetros', mm, 'Se souber (pluviômetro)'), field('Observação', notes), add);
  form.addEventListener('submit', busy(add, async () => {
    await adminApi('/api/admin/rain-events', {
      method: 'POST',
      json: { occurred_at: when.value || null, precipitation_mm: mm.value ? Number(mm.value) : null, notes: emptyToNull(notes.value) },
    });
    toast('Chuva registrada. Os selos de rega já consideram.');
    reload();
  }));

  const rows = events.map((e) => {
    const del = h('button', { type: 'button', class: 'btn btn-danger btn-small' }, 'Excluir');
    del.addEventListener('click', busy(del, async () => {
      if (!confirm('Excluir este registro de chuva?')) return;
      await adminApi(`/api/admin/rain-events/${e.id}`, { method: 'DELETE' });
      reload();
    }));
    return h('tr', {}, h('td', {}, fmtDateTime(e.occurred_at)),
      h('td', {}, e.precipitation_mm != null ? `${e.precipitation_mm} mm` : '—'),
      h('td', {}, e.notes || ''), h('td', {}, del));
  });

  return h('section', { class: 'card' },
    h('h2', {}, 'Chuva no campus'),
    h('p', { class: 'muted small' }, 'Chuva vale para todas as árvores plantadas: o selo passa a mostrar “Choveu há …”. Só o admin registra.'),
    form,
    events.length
      ? h('div', { class: 'table-wrap' }, h('table', {},
          h('thead', {}, h('tr', {}, ['Quando', 'Volume', 'Obs.', ''].map((c) => h('th', {}, c)))), h('tbody', {}, rows)))
      : h('p', { class: 'muted' }, 'Nenhuma chuva registrada.'));
}

function rulesCard(rules) {
  const anyPlaceholder = rules.some((r) => r.is_placeholder);
  return h('section', { class: 'card' },
    h('h2', {}, 'Regras de rega'),
    anyPlaceholder
      ? h('p', { class: 'notice notice-warn' }, '⚠️ Valores PLACEHOLDER: confirmar com NUGAI/Engenharia antes de usar como orientação.')
      : null,
    rules.map((rule) => {
      const interval = h('input', { type: 'number', min: '0.5', step: '0.5', value: rule.interval_days, required: true });
      const until = h('input', { type: 'number', min: '1', step: '1', value: rule.phase_until_days ?? '' });
      const confirmed = h('input', { type: 'checkbox', checked: !rule.is_placeholder });
      const note = h('input', { type: 'text', maxlength: '280', value: rule.note ?? '' });
      const save = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Salvar');
      const form = h('form', { class: 'grid-form rule' },
        h('h3', { class: 'wide' }, PHASES[rule.phase] || rule.phase),
        field('Intervalo entre regas (dias)', interval),
        rule.phase === 'newly_planted' ? field('Vale até quantos dias após o plantio', until) : null,
        field('Fonte / observação', note),
        h('label', { class: 'check' }, confirmed, ' Valor confirmado pela NUGAI/Engenharia'),
        save);
      form.addEventListener('submit', busy(save, async () => {
        const json = { interval_days: Number(interval.value), is_placeholder: !confirmed.checked, note: emptyToNull(note.value) };
        if (rule.phase === 'newly_planted') json.phase_until_days = until.value ? Number(until.value) : null;
        await adminApi(`/api/admin/watering-rules/${rule.id}`, { method: 'PATCH', json });
        toast('Regra salva.');
        reload();
      }));
      return form;
    }));
}

function originCard(origins) {
  return h('section', { class: 'card' }, h('h2', {}, 'Origem das mudas'), origins.map((o) => {
    const date = h('input', { type: 'date', value: o.donated_at ?? '' });
    const count = h('input', { type: 'number', min: '0', value: o.seedling_count ?? '' });
    const notes = h('input', { type: 'text', maxlength: '2000', value: o.notes ?? '' });
    const save = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Salvar');
    const form = h('form', { class: 'grid-form' }, h('h3', { class: 'wide' }, o.donor_name),
      field('Data da doação', date, 'Vazio aparece como “informação em revisão”'), field('Nº de mudas', count), field('Observações', notes), save);
    form.addEventListener('submit', busy(save, async () => {
      await adminApi(`/api/admin/origins/${o.id}`, {
        method: 'PATCH',
        json: { donated_at: date.value || null, seedling_count: count.value ? Number(count.value) : null, notes: emptyToNull(notes.value) },
      });
      toast('Origem salva.');
    }));
    return form;
  }));
}

export async function rainView() {
  const [events, rules, origins] = await Promise.all([
    adminApi('/api/admin/rain-events'), adminApi('/api/admin/watering-rules'), adminApi('/api/admin/origins'),
  ]);
  return [h('h1', {}, 'Chuva, regras e origem'), rainCard(events), rulesCard(rules), originCard(origins)];
}
