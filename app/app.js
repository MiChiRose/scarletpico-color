const $ = (selector) => document.querySelector(selector);
const layers = [...document.querySelectorAll('.screen-layer')];
const lcd = $('#lcd');
const emulatorFrame = $('#emulator');
let games = [];
let selected = 0;
let mode = 'off';
let activeGame = null;
let sessionStarted = 0;
let noticeTimer = 0;
let systemInputLockedUntil = 0;

function show(id) {
  layers.forEach((layer) => {
    const active = layer.id === id;
    layer.classList.toggle('active', active);
    layer.setAttribute('aria-hidden', String(!active));
  });
}

function gameKey(game, field) { return `scarletpico:stats:${game.id}:${field}`; }
function numberValue(key) { return Number(localStorage.getItem(key) || 0); }
function setNumber(key, value) { localStorage.setItem(key, String(value)); }

async function loadGames() {
  const response = await fetch('/api/games', {cache: 'no-store'});
  games = await response.json();
  selected = Math.min(selected, Math.max(0, games.length - 1));
  renderMenu();
}

function renderMenu() {
  $('#game-count').textContent = `${games.length} ${games.length === 1 ? 'GAME' : 'GAMES'}`;
  const list = $('#game-list');
  list.replaceChildren();
  if (!games.length) {
    const empty = document.createElement('li');
    empty.className = 'empty';
    empty.textContent = 'NO ROMS ON MICROSD';
    list.append(empty);
    return;
  }
  games.slice(Math.max(0, selected - 2), Math.max(0, selected - 2) + 5).forEach((game) => {
    const item = document.createElement('li');
    const index = games.indexOf(game);
    item.className = index === selected ? 'selected' : '';
    item.innerHTML = `<span>${index === selected ? '▶' : ''}</span><b>${game.name}</b><em>${game.system}</em>`;
    list.append(item);
  });
}

function playBootChime() {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return;
  const ctx = new AudioCtx();
  const gain = ctx.createGain();
  gain.connect(ctx.destination);
  gain.gain.setValueAtTime(0.0001, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.7);
  [[523.25, 0], [783.99, 0.13], [1046.5, 0.28]].forEach(([frequency, delay]) => {
    const osc = ctx.createOscillator();
    osc.type = 'triangle';
    osc.frequency.value = frequency;
    osc.connect(gain);
    osc.start(ctx.currentTime + delay);
    osc.stop(ctx.currentTime + delay + 0.26);
  });
  setTimeout(() => ctx.close(), 900);
}

async function powerOn() {
  if (mode !== 'off') return;
  mode = 'boot';
  await loadGames();
  show('boot-screen');
  setTimeout(playBootChime, 1250);
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  setTimeout(() => {
    mode = 'menu';
    show('menu-screen');
    renderMenu();
  }, reduced ? 700 : 3400);
}

function powerOff() {
  if (activeGame) closeGame();
  mode = 'off';
  activeGame = null;
  emulatorFrame.src = 'about:blank';
  show('power-screen');
}

function launchSelected() {
  if (!games.length) return;
  activeGame = games[selected];
  mode = 'game';
  sessionStarted = Date.now();
  emulatorFrame.src = `/app/emulator/index.html?rom=${encodeURIComponent(activeGame.path)}&id=${encodeURIComponent(activeGame.id)}`;
  show('game-screen');
  setTimeout(() => emulatorFrame.contentWindow?.focus(), 250);
}

function closeGame() {
  if (!activeGame) return;
  const elapsed = Math.max(0, Date.now() - sessionStarted);
  setNumber(gameKey(activeGame, 'playMs'), numberValue(gameKey(activeGame, 'playMs')) + elapsed);
  emulatorFrame.src = 'about:blank';
  activeGame = null;
  mode = 'menu';
  systemInputLockedUntil = performance.now() + 2000;
  show('menu-screen');
  renderMenu();
  lcd.focus();
}

function notice(message) {
  const el = $('#notice');
  el.textContent = message;
  el.classList.add('visible');
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => el.classList.remove('visible'), 1400);
}

function menuKey(event) {
  if (mode === 'off') { powerOn(); event.preventDefault(); return; }
  if (mode !== 'menu') return;
  if (performance.now() < systemInputLockedUntil && (event.code === 'Enter' || event.code === 'Tab')) {
    event.preventDefault();
    event.stopPropagation();
    return;
  }
  if (games.length && event.code === 'ArrowUp') selected = (selected + games.length - 1) % games.length;
  else if (games.length && event.code === 'ArrowDown') selected = (selected + 1) % games.length;
  else if (games.length && event.code === 'Tab') selected = (selected + 1) % games.length;
  else if (event.code === 'Enter') { launchSelected(); event.preventDefault(); return; }
  else return;
  renderMenu();
  event.preventDefault();
}

addEventListener('keydown', menuKey);
$('#power-button').addEventListener('click', () => mode === 'off' ? powerOn() : powerOff());
$('#power-screen').addEventListener('click', powerOn);
emulatorFrame.addEventListener('load', () => { if (mode === 'game') emulatorFrame.contentWindow?.focus(); });
addEventListener('message', (event) => {
  if (!event.data?.type?.startsWith('scarletpico:')) return;
  if (event.data.type === 'scarletpico:saved') notice('STATE SAVED');
  if (event.data.type === 'scarletpico:loaded') notice('STATE LOADED');
  if (event.data.type === 'scarletpico:notice') notice(event.data.message);
  if (event.data.type === 'scarletpico:exit') closeGame();
});

function updateClock() {
  const time = new Intl.DateTimeFormat('en-GB', {hour: '2-digit', minute: '2-digit', hour12: false}).format(new Date());
  $('#menu-time').textContent = time;
  $('#game-time').textContent = time;
}
updateClock();
setInterval(updateClock, 1000);
lcd.focus();
