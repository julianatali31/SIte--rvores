// Tiny DOM builder. Text always goes through textContent (no innerHTML with data).
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export const REVIEW_TEXT = 'informação em revisão';

export function orReview(value) {
  return value ? value : h('span', { class: 'muted' }, REVIEW_TEXT);
}

export function formatDate(isoDate) {
  if (!isoDate) return null;
  const [y, m, d] = isoDate.split('-');
  return `${d}/${m}/${y}`;
}
