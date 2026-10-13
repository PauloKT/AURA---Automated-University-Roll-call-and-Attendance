const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness(fetch) {
  const removed = [], events = {}, elements = new Map();
  const el = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', textContent: '', classList: { add() {}, remove() {} },
      addEventListener(name, callback) { this[name] = callback; },
      querySelector() { return el('submit'); },
    });
    return elements.get(id);
  };
  const context = {
    window: { location: { origin: 'https://aura.test', pathname: '/confirmar-presenca.html', search: '?sessaoId=1&token=scanned' } },
    document: {
      cookie: 'csrftoken=current-csrf', querySelector: () => ({ content: 'old-template-csrf' }),
      getElementById: el, addEventListener(name, callback) { events[name] = callback; },
    },
    localStorage: {
      removeItem(key) { removed.push(key); },
      getItem() { throw new Error('Não deve ler credenciais locais'); },
      setItem() { throw new Error('Não deve gravar credenciais locais'); },
    },
    URL, URLSearchParams, fetch,
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/js', 'api.js'), 'utf8'), context);
  context.Aura = context.window.Aura;
  return { context, api: context.Aura, removed, el, events };
}
const response = (data = {}, status = 200) => ({ ok: status < 400, status, json: async () => data });

for (const [description, data, expected] of [
  ['erro geral de login', { non_field_errors: ['Impossível fazer login com as credenciais fornecidas.'] }, 'Impossível fazer login com as credenciais fornecidas.'],
  ['erro de usuário', { username: ['Informe seu usuário ou e-mail.'] }, 'Informe seu usuário ou e-mail.'],
  ['erro de senha', { password: ['Informe sua senha.'] }, 'Informe sua senha.'],
  ['detalhe sem código técnico', { detail: 'Acesso negado.', code: 'permission_denied' }, 'Acesso negado.'],
  ['erro aninhado', { non_field_errors: { credentials: ['Credenciais inválidas.'] } }, 'Credenciais inválidas.'],
  ['campo com rótulo legível', { nome: ['Este campo é obrigatório.'] }, 'Nome: Este campo é obrigatório.'],
]) {
  test(`mensagem legível para ${description}`, async () => {
    const ui = harness(async () => response(data, 400));
    await assert.rejects(ui.api.json('/api/auth/login/', { method: 'POST' }), error => error.message === expected);
  });
}

test('envia cookie e CSRF atuais sem ler ou enviar JWT do armazenamento local', async () => {
  const ui = harness(async (url, options) => {
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.headers.Authorization, undefined);
    assert.equal(options.headers['X-CSRFToken'], 'current-csrf');
    assert.equal(options.headers['Content-Type'], 'application/json');
    return response();
  });
  await ui.api.json('/api/auth/login/', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  assert.deepEqual(ui.removed, ['access_token', 'refresh_token']);
});

test('consulta autenticada envia cookie sem cabeçalho CSRF desnecessário', async () => {
  const ui = harness(async (url, options) => {
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.headers['X-CSRFToken'], undefined);
    return response({ role: 'aluno' });
  });
  assert.equal((await ui.api.json('/api/interface/perfil/')).role, 'aluno');
});

test('sessão expirada redireciona para login preservando o link lido do QR', async () => {
  let requests = 0;
  const ui = harness(async () => { requests++; return response({}, 401); });
  await assert.rejects(ui.api.json('/api/interface/perfil/'), /sessão expirou/);
  assert.equal(requests, 1);
  const target = new URL(ui.context.window.location.href, 'https://aura.test');
  assert.equal(target.pathname, '/login.html');
  assert.equal(target.searchParams.get('next'), '/confirmar-presenca.html?sessaoId=1&token=scanned');
});

test('403 informa erro sem repetir envio ou redirecionar', async () => {
  let requests = 0;
  const ui = harness(async () => { requests++; return response({ detail: 'Sem permissão.' }, 403); });
  await assert.rejects(ui.api.json('/api/materias/', { method: 'POST' }), /Sem permissão/);
  assert.equal(requests, 1);
  assert.equal(ui.context.window.location.href, undefined);
});

test('não envia CSRF ou credenciais a outra origem', async () => {
  let requests = 0;
  const ui = harness(async () => { requests++; return response(); });
  await assert.rejects(ui.api.request('https://evil.test/', { method: 'POST' }), /mesmo endereço/);
  assert.equal(requests, 0);
});

for (const role of ['aluno', 'professor']) {
  test(`login ${role} funciona sem decodificar ou armazenar tokens`, async () => {
    const ui = harness(async (url, options) => {
      assert.equal(url, '/api/auth/login/');
      assert.deepEqual(JSON.parse(options.body), { username: 'usuario', password: 'senha' });
      return response({ user: { role } });
    });
    ui.context.window.location.search = '?next=' + encodeURIComponent('/confirmar-presenca.html?sessaoId=1&token=scanned');
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/js', 'login.js'), 'utf8'), ui.context);
    ui.events.DOMContentLoaded();
    ui.el('username').value = 'usuario'; ui.el('password').value = 'senha';
    await ui.el('login-form').submit({ preventDefault() {} });
    assert.equal(ui.context.window.location.href, role === 'aluno'
      ? '/confirmar-presenca.html?sessaoId=1&token=scanned' : 'professor.html');
  });
}
