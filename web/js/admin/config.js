let cached = null;

export async function getConfig() {
  if (!cached) cached = await (await fetch('/api/config')).json();
  return cached;
}

// Views return their DOM before it is attached; maps need a sized container.
export function afterMount(fn) {
  setTimeout(fn, 0);
}
