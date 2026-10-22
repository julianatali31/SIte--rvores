import { h } from '../dom.js';
import { adminApi, getToken, setToken } from './http.js';
import { busy, field } from './ui.js';
import { treeList } from './views/trees.js';
import { treeDetail } from './views/tree-detail.js';
import { speciesList, speciesForm } from './views/species.js';
import { zoneView } from './views/zone.js';
import { rainView } from './views/rain.js';
import { labelsView } from './views/labels.js';

const view = document.getElementById('view');
const nav = document.getElementById('nav');

const ROUTES = [
  [/^#\/arvores\/(\d+)$/, (m) => treeDetail(Number(m[1]))],
  [/^#\/arvores$/, () => treeList()],
  [/^#\/especies\/(nova|\d+)$/, (m) => speciesForm(m[1] === 'nova' ? null : Number(m[1]))],
  [/^#\/especies$/, () => speciesList()],
  [/^#\/zona$/, () => zoneView()],
  [/^#\/chuva$/, () => rainView()],
  [/^#\/etiquetas$/, () => labelsView()],
];

function loginView() {
  const username = h('input', { name: 'username', autocomplete: 'username', required: true });
  const password = h('input', { name: 'password', type: 'password', autocomplete: 'current-password', required: true });
  const button = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Entrar');
  const form = h('form', { class: 'card login' },
    h('h1', {}, 'Entrar'), field('Usuário', username), field('Senha', password), button);
  form.addEventListener('submit', busy(button, async () => {
    const result = await adminApi('/api/admin/login', {
      method: 'POST', json: { username: username.value, password: password.value },
    });
    setToken(result.access_token);
    location.hash = '#/arvores';
  }));
  return form;
}

async function route() {
  const hash = location.hash || '#/arvores';
  const loggedIn = Boolean(getToken());
  nav.hidden = !loggedIn;
  if (!loggedIn || hash === '#/login') {
    if (loggedIn) { location.hash = '#/arvores'; return; }
    view.replaceChildren(loginView());
    return;
  }
  for (const link of nav.querySelectorAll('a')) {
    link.classList.toggle('active', hash.startsWith(link.getAttribute('href')));
  }
  const match = ROUTES.map(([re, render]) => [hash.match(re), render]).find(([m]) => m);
  view.replaceChildren(h('p', { class: 'loading' }, 'Carregando…'));
  try {
    const content = match ? await match[1](match[0]) : h('p', {}, 'Página não encontrada.');
    view.replaceChildren(...[content].flat());
  } catch (err) {
    view.replaceChildren(h('div', { class: 'card' }, h('h2', {}, 'Erro'), h('p', {}, err.message || String(err))));
  }
}

document.getElementById('logout').addEventListener('click', () => {
  setToken(null);
  location.hash = '#/login';
});
window.addEventListener('hashchange', route);
route();
