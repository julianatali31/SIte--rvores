import { h } from '../dom.js';

export const STATUS_LABELS = {
  awaiting_planting: 'Aguardando plantio',
  planted: 'Plantada',
  attention: 'Atenção',
  dead: 'Morta',
};
export const CARE_LABELS = { watering: 'Rega', fertilizing: 'Adubação', pruning: 'Poda', other: 'Outro' };
export const BADGE_LABELS = { green: 'Em dia', yellow: 'Perto de vencer', red: 'Atrasada', grey: 'Sem registro' };

const dtf = new Intl.DateTimeFormat('pt-BR', {
  timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
});

export function fmtDateTime(iso) {
  return iso ? dtf.format(new Date(iso)) : '—';
}

// Value for <input type="datetime-local"> in São Paulo time.
export function localInputValue(date = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(date).map((p) => [p.type, p.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function statusChip(status) {
  return h('span', { class: `chip status-${status}` }, STATUS_LABELS[status] || status);
}

export function badgeDot(color, text) {
  if (!color) return h('span', { class: 'muted' }, '—');
  return h('span', { class: `dot dot-${color}` }, text || BADGE_LABELS[color]);
}

export function field(label, input, hint) {
  const id = input.id || `f-${Math.random().toString(36).slice(2, 8)}`;
  input.id = id;
  return h('div', { class: 'field' }, h('label', { for: id }, label), input, hint ? h('small', { class: 'muted' }, hint) : null);
}

export function select(name, options, value, { allowEmpty = false, emptyLabel = '—' } = {}) {
  return h('select', { name },
    allowEmpty ? h('option', { value: '' }, emptyLabel) : null,
    options.map(([v, label]) => h('option', { value: String(v), selected: String(v) === String(value ?? '') }, label)));
}

export function toast(message, kind = 'ok') {
  const el = h('div', { class: `toast toast-${kind}`, role: 'status' }, message);
  document.body.append(el);
  setTimeout(() => el.remove(), kind === 'error' ? 6000 : 3000);
}

export function errorText(err) {
  return err?.message || 'Algo deu errado.';
}

// Wraps an async click/submit handler: disables the button and reports errors.
export function busy(button, fn) {
  return async (event) => {
    event?.preventDefault?.();
    button.disabled = true;
    try {
      await fn(event);
    } catch (err) {
      toast(errorText(err), 'error');
    } finally {
      button.disabled = false;
    }
  };
}

export function emptyToNull(value) {
  const v = typeof value === 'string' ? value.trim() : value;
  return v === '' || v === undefined ? null : v;
}
