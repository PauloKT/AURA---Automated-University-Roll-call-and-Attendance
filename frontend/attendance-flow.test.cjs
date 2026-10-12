const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const flush = () => new Promise(resolve => setImmediate(resolve));
const response = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data });
const prepared = { comprovante: 'signed', turma: 'Turma A', aula: 'Aula 1' };
const svg = value => 'data:image/svg+xml;base64,' + Buffer.from(`<svg>${value}</svg>`).toString('base64');
const token = value => ({
  token_atual: value, qr_image: svg(value),
  servidor_agora: '2026-10-01T12:00:00Z', token_expira_em: '2026-10-01T12:00:30Z',
});
function deferred() {
  let resolve;
  const promise = new Promise(accept => { resolve = accept; });
  return { promise, resolve };
}

function harness(file, fetch) {
  const elements = new Map(), events = {}, intervals = new Map(), timers = new Map();
  let sequence = 0, now = 0, locate;
  function makeElement() {
    const classes = new Set();
    return {
      style: {}, value: '', hidden: false, disabled: false, textContent: '', children: [], listeners: {},
      classList: { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name) },
      addEventListener(name, callback) { this.listeners[name] = callback; },
      dispatchEvent(event) { return this.listeners[event.type]?.call(this, event); },
      removeAttribute(name) { delete this[name]; }, setAttribute(name, value) { this[name] = value; },
      appendChild(item) { this.children.push(item); }, replaceChildren(...items) { this.children = items; },
    };
  }
  const element = id => { if (!elements.has(id)) elements.set(id, makeElement()); return elements.get(id); };
  const context = {
    document: {
      hidden: false, cookie: 'csrftoken=test', getElementById: element, createElement: makeElement,
      addEventListener(name, callback) { events[name] = callback; },
    },
    window: {
      isSecureContext: true,
      location: { hostname: 'aura.test', origin: 'https://aura.test', pathname: '/confirmar-presenca.html', search: '?sessaoId=1&token=scanned' },
      addEventListener(name, callback) { events[name] = callback; }, dispatchEvent() {},
    },
    localStorage: { getItem: () => 'authenticated' },
    navigator: { geolocation: { getCurrentPosition(success, error) { locate = { success, error }; } } },
    // Um relógio de dispositivo adiantado não deve impedir a rotação.
    Date: class extends Date { static now() { return Date.parse('2030-01-01T00:00:00Z'); } },
    performance: { now: () => now },
    URL, URLSearchParams, Event: class { constructor(type) { this.type = type; } }, fetch, alert() {},
    setTimeout(callback, delay) { const id = ++sequence; timers.set(id, { callback, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    setInterval(callback) { const id = ++sequence; intervals.set(id, callback); return id; },
    clearInterval(id) { intervals.delete(id); },
  };
  context.location = context.window.location;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'api.js'), 'utf8'), context);
  context.Aura = context.window.Aura;
  vm.runInContext(fs.readFileSync(path.join(__dirname, file), 'utf8'), context);
  const ready = events.DOMContentLoaded();
  return {
    element, events, intervals, timers, ready,
    get locate() { return locate; },
    click: id => element(id).dispatchEvent({ type: 'click' }),
    advance(ms) { now += ms; for (const tick of [...intervals.values()]) tick(); },
    runTimers(delay) {
      for (const [id, timer] of [...timers]) {
        if (timer.delay === delay) { timers.delete(id); timer.callback(); }
      }
    },
  };
}

async function startCall(fetchSession) {
  const ui = harness('professor.js', async (url, options) => {
    if (url === '/api/materias/') return response([]);
    if (url === '/api/sessoes/') return response({ id: 1, professor_radius_meters: 100 });
    if (url.endsWith('/resultados/')) return response({ ativa: true, resultados: [] });
    return fetchSession(url, options);
  });
  ui.element('aula-select').value = '1';
  await ui.click('start-session-btn');
  await flush();
  return ui;
}

for (const failure of [response({ presenca: { valida: false } }, 201), response({ detail: 'Fora do raio.' }, 400)]) {
  test(`falha HTTP ${failure.status} permite nova captura GPS e só confirma valida=true`, async () => {
    let registrations = 0, preparations = 0;
    const ui = harness('confirmar-presenca.js', async (url, options) => {
      if (url.endsWith('/preparar/')) { preparations++; return response(prepared); }
      const body = JSON.parse(options.body);
      assert.equal(body.comprovante, 'signed');
      return ++registrations === 1 ? failure : response({ presenca: { valida: true } }, 201);
    });
    await flush();
    ui.locate.success({ coords: { latitude: -21, longitude: -51.66 } });
    await ui.ready;
    assert.equal(ui.element('confirm-btn').hidden, false);
    assert.equal(ui.element('confirm-btn').disabled, false);
    assert.equal(ui.element('success-message').classList.contains('show'), false);
    const retry = ui.click('confirm-btn');
    ui.locate.success({ coords: { latitude: -20.78, longitude: -51.66 } });
    await retry;
    assert.equal(ui.element('success-message').textContent, 'Presença confirmada com sucesso!');
    assert.equal(ui.element('confirm-btn').hidden, true);
    await ui.click('confirm-btn');
    assert.equal(registrations, 2);
    assert.equal(preparations, 1);
  });
}

test('QR expirado não solicita GPS nem exibe sucesso', async () => {
  const ui = harness('confirmar-presenca.js', async () => response({ detail: 'Leia o QR Code atual.' }, 400));
  await ui.ready;
  assert.equal(ui.locate, undefined);
  assert.equal(ui.element('error-message').textContent, 'Leia o QR Code atual.');
  assert.equal(ui.element('success-message').classList.contains('show'), false);
});

test('QR local gira após 30s mesmo com relógio do dispositivo incorreto', async () => {
  let queries = 0;
  const ui = await startCall(async url => {
    assert.equal(url, '/api/sessoes/1/token/?origin=https%3A%2F%2Faura.test');
    return response(token(String(++queries)));
  });
  assert.equal(ui.element('qr-code-img').src, svg('1'));
  assert.equal(ui.element('countdown').textContent, '00:30');
  ui.advance(30000);
  assert.equal(ui.element('qr-code-img').src, undefined);
  ui.runTimers(250);
  await flush();
  assert.equal(ui.element('qr-code-img').src, svg('2'));
  assert.equal(queries, 2);
  assert.equal(ui.intervals.size, 1);
});

test('falha temporária de renovação remove QR vencido e tenta novamente sozinha', async () => {
  let queries = 0;
  const ui = await startCall(async () => {
    if (++queries === 2) throw new Error('Sem conexão');
    return response(token(String(queries)));
  });
  ui.advance(30000); ui.runTimers(250); await flush();
  assert.equal(ui.element('qr-code-img').src, undefined);
  assert.equal(ui.element('countdown').textContent, 'Tentando atualizar…');
  ui.runTimers(3000); await flush();
  assert.equal(ui.element('qr-code-img').src, svg('3'));
});

test('cliques sobrepostos compartilham uma única requisição de QR', async () => {
  const pending = deferred();
  let queries = 0;
  const ui = await startCall(async () => { queries++; return pending.promise; });
  ui.click('refresh-results-btn'); ui.click('refresh-results-btn');
  assert.equal(queries, 1);
  pending.resolve(response(token('current'))); await flush();
  assert.equal(ui.element('qr-code-img').src, svg('current'));
  assert.equal(ui.intervals.size, 1);
});

test('QR recebido depois da seleção de outra aula é descartado', async () => {
  const pending = deferred();
  const ui = await startCall(async () => pending.promise);
  ui.element('aula-select').value = '2';
  ui.element('aula-select').dispatchEvent({ type: 'change' });
  pending.resolve(response(token('stale'))); await flush();
  assert.equal(ui.element('qr-code-img').src, undefined);
  assert.equal(ui.intervals.size, 0);
  assert.equal(ui.timers.size, 0);
});

test('encerrar cancela repetição automática de QR', async () => {
  let queries = 0;
  const ui = await startCall(async url => {
    if (url.endsWith('/encerrar/')) return response({});
    queries++; throw new Error('Sem conexão');
  });
  await ui.click('end-session-btn'); await flush();
  ui.runTimers(3000); await flush();
  assert.equal(queries, 1);
  assert.equal(ui.element('qr-code-img').src, undefined);
  assert.equal(ui.element('call-state').textContent, 'Chamada encerrada');
  assert.equal(ui.intervals.size, 0);
  assert.equal(ui.timers.size, 0);
});

test('resposta de QR que já venceu aguarda antes de consultar novamente', async () => {
  let queries = 0;
  const ui = await startCall(async () => {
    queries++;
    return response({ ...token('expired'), token_expira_em: '2026-10-01T11:59:59Z' });
  });
  assert.equal(ui.element('qr-code-img').src, undefined);
  assert.equal(queries, 1);
  assert.equal(ui.intervals.size, 0);
  ui.runTimers(250); await flush();
  assert.equal(queries, 2);
});
