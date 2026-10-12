import Lenis from 'lenis';
import { animate } from 'framer-motion/dom/mini';

const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let scroll: Lenis | undefined;
let wheelDirection = 0;
let themeBusy = false;
let themeAnimation: Animation | undefined;
const entrances = new Map<HTMLElement, ReturnType<typeof animate>>();

function syncScroll(): void {
  const active = !reduced.matches && !document.body.classList.contains('signed-out') &&
    document.visibilityState === 'visible' && !document.fullscreenElement && !document.querySelector('dialog[open]');
  if (active && !scroll) scroll = new Lenis({
    autoRaf: true, lerp: .22, respectReducedMotion: true, overscroll: false,
    virtualScroll: ({ deltaY, event }) => {
      if (event.type !== 'wheel' || event.ctrlKey || !(event.target instanceof HTMLElement) ||
          event.target.closest('[data-lenis-prevent], dialog, #authGate, #messages, #ngchatMessages, #reviewPanel, textarea, select')) return false;
      const direction = Math.sign(deltaY);
      if (direction && wheelDirection && direction !== wheelDirection) {
        // Discard the old target when input reverses; continue smoothly from the current visible position.
        scroll?.scrollTo(scroll.actualScroll, { immediate: true, force: true });
      }
      if (direction) wheelDirection = direction;
      return true;
    },
    prevent: node => Boolean(node.closest('[data-lenis-prevent], dialog, #authGate, #messages, #ngchatMessages, #reviewPanel, textarea, select'))
  });
  else if (!active && scroll) { scroll.destroy(); scroll = undefined; wheelDirection = 0; }
}
function clearEntrances(): void {
  for (const [element, control] of entrances) {
    control.cancel(); element.style.removeProperty('opacity'); element.style.removeProperty('transform');
  }
  entrances.clear();
}
function enter(element: HTMLElement, delay = 0): void {
  if (reduced.matches || document.fullscreenElement || !element.getClientRects().length) return;
  entrances.get(element)?.cancel();
  const control = animate(element, { opacity: [0, 1], transform: ['translateY(8px)', 'translateY(0px)'] },
    { duration: .38, delay, ease: [.22, 1, .36, 1] });
  entrances.set(element, control);
  void control.then(() => {
    if (entrances.get(element) !== control) return;
    entrances.delete(element); element.style.removeProperty('opacity'); element.style.removeProperty('transform');
  });
}
function enterView(): void {
  clearEntrances();
  const selector = document.getElementById('profilePane')?.hidden ?
    '.studio-heading, .source-bar' : '#profilePane .profile-heading, #profilePane .profile-section';
  document.querySelectorAll<HTMLElement>(selector).forEach((element, index) => enter(element, Math.min(index * .035, .14)));
}
function themeSnapshot(theme: string): HTMLDivElement {
  const source = document.getElementById('root');
  if (!source) throw new Error('Missing studio surface.');
  const snapshot = document.createElement('div');
  snapshot.className = 'theme-snapshot'; snapshot.dataset.theme = theme;
  snapshot.setAttribute('aria-hidden', 'true'); snapshot.inert = true;
  const clone = source.cloneNode(true) as HTMLElement;
  clone.style.marginTop = `${-window.scrollY}px`;
  const originals = [source, ...source.querySelectorAll<HTMLElement>('*')];
  const copies = [clone, ...clone.querySelectorAll<HTMLElement>('*')];
  originals.forEach((original, index) => {
    const copy = copies[index];
    // Namespace IDs so controllers and labels always address the live React tree.
    if (copy.id) { copy.dataset.snapshotId = copy.id; copy.removeAttribute('id'); }
    if (original instanceof HTMLInputElement && copy instanceof HTMLInputElement) {
      // A cloned checked radio must not join and unset the live result radio group.
      copy.removeAttribute('name');
      copy.value = ['password', 'file'].includes(original.type) ? '' : original.value; copy.checked = original.checked;
    } else if (original instanceof HTMLTextAreaElement && copy instanceof HTMLTextAreaElement) copy.value = original.value;
    else if (original instanceof HTMLSelectElement && copy instanceof HTMLSelectElement) copy.value = original.value;
    if (original instanceof HTMLCanvasElement && copy instanceof HTMLCanvasElement) {
      copy.getContext('2d')?.drawImage(original, 0, 0);
    } else if (original instanceof HTMLVideoElement && original.readyState >= 2) {
      const frame = document.createElement('canvas');
      frame.width = original.videoWidth; frame.height = original.videoHeight;
      frame.className = copy.className; frame.dataset.snapshotId = copy.dataset.snapshotId;
      const mediaStyle = getComputedStyle(original);
      Object.assign(frame.style, { display: 'block', width: mediaStyle.width, height: mediaStyle.height,
        objectFit: mediaStyle.objectFit, objectPosition: mediaStyle.objectPosition, background: mediaStyle.backgroundColor });
      try { frame.getContext('2d')?.drawImage(original, 0, 0); copy.replaceWith(frame); } catch { /* Keep the poster if a frame is unavailable. */ }
    }
    if (getComputedStyle(original).position === 'sticky') {
      const box = original.getBoundingClientRect();
      Object.assign(copy.style, { position: 'fixed', left: `${box.left}px`, top: `${box.top}px`, width: `${box.width}px`, height: `${box.height}px` });
    }
  });
  snapshot.append(clone); document.body.append(snapshot);
  // Scroll offsets clamp to zero while detached; restore after the copy has layout.
  originals.forEach((original, index) => { copies[index].scrollTop = original.scrollTop; copies[index].scrollLeft = original.scrollLeft; });
  return snapshot;
}
async function revealTheme(apply: () => void): Promise<void> {
  if (themeBusy) return;
  if (reduced.matches || document.fullscreenElement) { apply(); return; }
  const root = document.documentElement;
  const toggle = document.getElementById('themeToggleBtn') as HTMLButtonElement;
  const selection = document.getElementById('themeSelect') as HTMLSelectElement;
  const rect = toggle.getBoundingClientRect(), x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
  const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  themeBusy = true; toggle.disabled = true; selection.disabled = true; root.classList.add('theme-reveal');
  let snapshot: HTMLDivElement | undefined;
  let applied = false;
  const commitTheme = () => { if (!applied) { apply(); applied = true; } };
  try {
    const choice = selection.value;
    const theme = choice === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : choice;
    // ponytail: reveal a frozen copy of the real UI; live video stays mounted and continues underneath.
    snapshot = themeSnapshot(theme);
    themeAnimation = snapshot.animate({ clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
      { duration: 900, easing: 'cubic-bezier(.4,0,.2,1)', fill: 'forwards' });
    await themeAnimation.finished;
    commitTheme();
    getComputedStyle(root).color; // Flush the new palette while color transitions are disabled.
  } catch { commitTheme(); }
  finally {
    themeAnimation?.cancel(); themeAnimation = undefined; themeBusy = false; snapshot?.remove();
    toggle.disabled = false; selection.disabled = false; root.classList.remove('theme-reveal');
  }
}

document.addEventListener('workspace-theme', event => {
  const apply = (event as CustomEvent<() => void>).detail;
  if (typeof apply !== 'function') return;
  event.preventDefault(); void revealTheme(apply);
});
document.addEventListener('workspace-ready', () => { syncScroll(); enterView(); });
document.addEventListener('workspace-view', () => { scroll?.resize(); wheelDirection = 0; enterView(); });
document.addEventListener('workspace-message', event => {
  const element = (event as CustomEvent<HTMLElement>).detail;
  if (element instanceof HTMLElement) enter(element);
});
reduced.addEventListener('change', () => {
  if (reduced.matches) { clearEntrances(); themeAnimation?.cancel(); }
  syncScroll();
});
new MutationObserver(syncScroll).observe(document.body, { attributes: true, attributeFilter: ['class'] });
document.addEventListener('fullscreenchange', () => { themeAnimation?.cancel(); syncScroll(); });
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') themeAnimation?.cancel(); syncScroll(); });
window.addEventListener('resize', () => themeAnimation?.cancel());
document.addEventListener('scroll', () => themeAnimation?.cancel(), { passive: true });
document.addEventListener('toggle', syncScroll, true);
window.addEventListener('pagehide', () => { scroll?.destroy(); scroll = undefined; wheelDirection = 0; clearEntrances(); themeAnimation?.cancel(); });
window.addEventListener('pageshow', syncScroll);
syncScroll();
