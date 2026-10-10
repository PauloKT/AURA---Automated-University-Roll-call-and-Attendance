document.addEventListener('DOMContentLoaded', function() {
  const loading = document.getElementById('loading');
  const content = document.getElementById('content');
  const list = document.getElementById('turmas-list');
  const calls = document.getElementById('calls-list');
  const callsStatus = document.getElementById('calls-status');
  const joinForm = document.getElementById('join-form');
  const inviteInput = document.getElementById('invite-code');
  const joinMessage = document.getElementById('join-message');
  let polling = null;
  let busy = false;
  let stopped = false;
  let previousCalls = '';

  inviteInput.value = new URLSearchParams(window.location.search).get('convite') || '';

  async function loadGroups() {
    const { turmas } = await Aura.json('/api/aluno/turmas/');
    list.replaceChildren();
    if (!turmas.length) {
      list.innerHTML = UI.empty('Sua primeira turma começa aqui', 'Peça o código ao professor para acompanhar as aulas e sua frequência.', '<a class="button" href="#entrar">Entrar em uma turma</a>');
    }
    for (const turma of turmas) {
      const card = document.createElement('div');
      card.className = 'turma-card';
      const e = UI.escape;
      const hasFrequency = ['aprovado', 'reprovado'].includes(turma.situacao);
      card.innerHTML = `<span class="course-code">${e(turma.materia.nome)}</span>
        <h3>${e(turma.nome)}</h3>
        <p class="muted">${e(turma.semestre)} / ${e(turma.ano)}<br>Professor: ${e(turma.professor || 'Não informado')}</p>
        <div class="student-card-frequency"><div><small>Sua frequência</small><strong>${hasFrequency ? UI.percent(turma.percentual) : 'Sem dados'}</strong></div>${UI.badge(hasFrequency ? turma.situacao : 'sem_dados')}</div>
        <progress max="100" value="${hasFrequency ? Number(turma.percentual) || 0 : 0}" aria-label="Frequência em ${e(turma.materia.nome)}"></progress>
        <div class="card-meta"><span>${e(turma.presencas ?? 0)} presenças</span><span>${e(turma.faltas ?? 0)} faltas</span></div>`;
      list.appendChild(card);
    }
  }

  async function checkCalls() {
    if (busy || stopped || document.hidden) return;
    busy = true;
    try {
      const { chamadas } = await Aura.json('/api/sessoes/ativas/');
      const signature = JSON.stringify(chamadas);
      if (signature !== previousCalls) {
        calls.replaceChildren();
        for (const chamada of chamadas) {
          const notice = document.createElement('div');
          notice.className = 'turma-card';
          const title = document.createElement('h3');
          title.textContent = `Chamada iniciada: ${chamada.materia}`;
          const detail = document.createElement('p');
          detail.textContent = `${chamada.turma} — ${chamada.aula}. Leia o QR Code exibido pelo professor para confirmar sua presença.`;
          notice.append(title, detail);
          calls.appendChild(notice);
        }
        previousCalls = signature;
      }
      callsStatus.textContent = chamadas.length ? 'Há chamada aguardando sua presença.' : 'Nenhuma chamada aberta agora. Os avisos são atualizados automaticamente.';
    } catch (error) {
      callsStatus.textContent = 'Não foi possível atualizar os avisos. Tentaremos novamente.';
    } finally {
      busy = false;
      clearTimeout(polling);
      if (!stopped) polling = setTimeout(checkCalls, 5000);
    }
  }

  joinForm.addEventListener('submit', async event => {
    event.preventDefault();
    const button = document.getElementById('join-btn');
    button.disabled = true;
    try {
      let code = inviteInput.value.trim();
      if (/^https?:\/\//i.test(code)) code = new URL(code).searchParams.get('convite') || '';
      const invitation = /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(code)
        ? { link_acesso: code } : { codigo_acesso: code.toUpperCase() };
      const data = await Aura.json('/api/aluno/entrar-turma/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(invitation)
      });
      joinMessage.textContent = data.detail;
      joinMessage.className = 'success show';
      window.dispatchEvent(new Event('aura:joined'));
      inviteInput.value = '';
      await loadGroups();
      await checkCalls();
    } catch (error) {
      joinMessage.textContent = error.message;
      joinMessage.className = 'error show';
    } finally {
      button.disabled = false;
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) { clearTimeout(polling); checkCalls(); }
  });
  window.addEventListener('pagehide', () => { stopped = true; clearTimeout(polling); });
  window.addEventListener('pageshow', () => { if (stopped) { stopped = false; checkCalls(); } });

  loadGroups().then(checkCalls).catch(error => {
    list.textContent = error.message;
  }).finally(() => {
    loading.style.display = 'none';
    content.style.display = 'block';
  });
});
