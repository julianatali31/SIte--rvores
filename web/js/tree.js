import { api, ApiError } from './api.js';
import { h, orReview, formatDate, REVIEW_TEXT } from './dom.js';
import { renderMiniMap } from './minimap.js';

const app = document.getElementById('app');
const publicId = location.pathname.split('/').filter(Boolean).pop();
const NAME_KEY = 'plantando-ideias:name';

const BADGE_ICON = { green: '✓', yellow: '!', red: '✕', grey: '?' };

function storedName() {
  try { return localStorage.getItem(NAME_KEY) || ''; } catch { return ''; }
}
function rememberName(name) {
  try { name ? localStorage.setItem(NAME_KEY, name) : localStorage.removeItem(NAME_KEY); } catch { /* private mode */ }
}

function titleBlock(tree) {
  return h('section', { class: 'title' },
    h('h1', {}, tree.species.common_name),
    tree.species.scientific_name
      ? h('p', { class: 'scientific' }, h('i', {}, tree.species.scientific_name),
          tree.species.data_review_status === 'pending' ? h('span', { class: 'muted' }, ' (nome em revisão)') : null)
      : h('p', { class: 'scientific muted' }, REVIEW_TEXT),
    h('p', { class: 'meta' },
      h('span', { class: 'chip' }, tree.code),
      tree.age_text ? h('span', {}, tree.age_text) : null,
      tree.status === 'attention' ? h('span', { class: 'chip chip-warn' }, 'Em atenção') : null),
  );
}

function heroPhoto(tree) {
  const latest = tree.photos.at(-1);
  const url = latest?.url || tree.species.photo_url;
  if (!url) return h('div', { class: 'hero hero-empty', 'aria-hidden': 'true' }, '🌳');
  return h('img', { class: 'hero', src: url, alt: `Foto da árvore ${tree.code}` });
}

function badgeBlock(badge) {
  return h('section', { class: `badge badge-${badge.color}`, id: 'badge', role: 'status' },
    h('div', { class: 'badge-icon', 'aria-hidden': 'true' }, BADGE_ICON[badge.color]),
    h('div', { class: 'badge-text' },
      h('p', { class: 'badge-headline' }, badge.headline),
      badge.detail ? h('p', { class: 'badge-detail' }, `(${badge.detail})`) : null,
      h('p', { class: 'badge-hint' }, badge.hint),
      badge.due_text ? h('p', { class: 'badge-due' }, badge.due_text) : null,
      badge.last_water_source === 'rain' && badge.last_watering_text
        ? h('p', { class: 'badge-due' }, `Última rega manual: ${badge.last_watering_text}`) : null,
    ),
  );
}

function waterForm(tree, onDone) {
  const nameInput = h('input', {
    id: 'name', name: 'name', type: 'text', maxlength: '60', autocomplete: 'given-name',
    placeholder: 'Seu nome (opcional)', value: storedName(),
  });
  // Honeypot: off-screen, not focusable, ignored by people.
  const trap = h('div', { class: 'hp', 'aria-hidden': 'true' },
    h('label', { for: 'website' }, 'Não preencha'),
    h('input', { id: 'website', name: 'website', type: 'text', tabindex: '-1', autocomplete: 'off' }));
  const button = h('button', { type: 'submit', class: 'btn-water' }, '💧 Reguei agora');
  const feedback = h('p', { class: 'feedback', role: 'alert' });

  const form = h('form', { class: 'water-form', novalidate: true },
    tree.badge?.recent_rain
      ? h('p', { class: 'notice' }, '🌧️ Choveu nas últimas horas, talvez não precise regar.') : null,
    h('label', { for: 'name', class: 'sr-only' }, 'Seu nome (opcional)'),
    nameInput, trap, button, feedback);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    button.disabled = true;
    button.textContent = 'Registrando…';
    feedback.textContent = '';
    feedback.className = 'feedback';
    const name = nameInput.value.trim();
    try {
      const result = await api(`/api/trees/${publicId}/waterings`, {
        method: 'POST',
        body: { name: name || null, website: form.website.value || null },
      });
      rememberName(name);
      onDone(result.tree, result.message, 'ok');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.body?.tree) {
        onDone(err.body.tree, err.body.detail, 'info');
        return;
      }
      const message = err instanceof ApiError
        ? (err.status === 422 ? 'Confira o nome (máximo 60 caracteres).' : err.message)
        : 'Sem conexão. Tente de novo.';
      feedback.textContent = message;
      feedback.classList.add('feedback-error');
      button.disabled = false;
      button.textContent = '💧 Reguei agora';
    }
  });
  return form;
}

function waterings(list) {
  return h('section', { class: 'card' },
    h('h2', {}, 'Últimas regas'),
    list.length
      ? h('ul', { class: 'list' }, list.map((w) => h('li', {}, h('strong', {}, w.who), h('span', {}, w.when_text))))
      : h('p', { class: 'muted' }, 'Nenhuma rega registrada ainda.'));
}

function species(tree) {
  const s = tree.species;
  const row = (label, value) => [h('dt', {}, label), h('dd', {}, orReview(value))];
  return h('section', { class: 'card' },
    h('h2', {}, 'Sobre a espécie'),
    s.data_review_status === 'pending'
      ? h('p', { class: 'notice' }, 'As informações desta espécie ainda estão em revisão pela equipe do projeto.') : null,
    s.description ? h('p', {}, s.description) : null,
    h('dl', { class: 'facts' },
      row('Porte', s.size_class),
      row('Raízes', s.root_notes),
      row('Época de frutos', s.fruiting_season),
      row('Curiosidade', s.fun_fact)));
}

function origin(tree) {
  return h('section', { class: 'card' },
    h('h2', {}, 'Origem'),
    h('dl', { class: 'facts' },
      h('dt', {}, 'Muda doada por'), h('dd', {}, tree.origin.donor_name),
      h('dt', {}, 'Data da doação'), h('dd', {}, orReview(formatDate(tree.origin.donated_at))),
      tree.zone_name ? [h('dt', {}, 'Local'), h('dd', {}, tree.zone_name)] : null));
}

function photos(list) {
  if (!list.length) return null;
  return h('section', { class: 'card' },
    h('h2', {}, 'Fotos ao longo do tempo'),
    h('ol', { class: 'timeline' }, list.map((p) => h('li', {},
      h('img', { src: p.url, alt: p.caption || `Foto de ${p.taken_label}`, loading: 'lazy' }),
      h('span', {}, p.taken_label),
      p.caption ? h('span', { class: 'muted' }, p.caption) : null))));
}

function miniMapSection(tree) {
  if (!tree.location) return null;
  const box = h('div', { class: 'minimap', role: 'img', 'aria-label': 'Localização da árvore no mapa' });
  queueMicrotask(() => renderMiniMap(box, tree.location, tree.badge?.color));
  return h('section', { class: 'card' }, h('h2', {}, 'Onde fica'), box,
    h('p', {}, h('a', { href: `/mapa#${tree.public_id}` }, 'Abrir no mapa do campus')));
}

function simplePage(tree, emoji, title, text) {
  return [
    h('div', { class: 'hero hero-empty', 'aria-hidden': 'true' }, emoji),
    titleBlock(tree),
    h('section', { class: 'card card-highlight' }, h('h2', {}, title), h('p', {}, text)),
    species(tree),
    origin(tree),
  ];
}

function render(tree, message, kind) {
  document.title = `${tree.species.common_name} (${tree.code}) · Plantando Ideias`;
  let content;
  if (tree.status === 'awaiting_planting') {
    content = simplePage(tree, '🌱', 'Esta muda ainda aguarda o local de plantio',
      'Ela faz parte das mudas doadas ao campus e será plantada assim que o local for definido.');
  } else if (tree.status === 'dead') {
    content = simplePage(tree, '🍂', 'Esta árvore não sobreviveu',
      'Obrigado a todos que cuidaram dela. O registro fica guardado para a história do projeto.');
  } else {
    content = [
      heroPhoto(tree),
      titleBlock(tree),
      badgeBlock(tree.badge),
      tree.can_water ? waterForm(tree, render) : null,
      message ? h('p', { class: `flash flash-${kind}`, role: 'status' }, message) : null,
      waterings(tree.recent_waterings),
      photos(tree.photos),
      species(tree),
      origin(tree),
      miniMapSection(tree),
    ];
  }
  app.replaceChildren(...content.flat().filter(Boolean));
  if (message) document.getElementById('badge')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function main() {
  try {
    render(await api(`/api/trees/${publicId}`));
  } catch (err) {
    const notFound = err instanceof ApiError && err.status === 404;
    app.replaceChildren(h('section', { class: 'card card-highlight' },
      h('h1', {}, notFound ? 'Árvore não encontrada' : 'Não foi possível carregar'),
      h('p', {}, notFound ? 'Confira o endereço ou leia o QR Code da placa de novo.' : 'Verifique a conexão e tente de novo.')));
  }
}

main();
