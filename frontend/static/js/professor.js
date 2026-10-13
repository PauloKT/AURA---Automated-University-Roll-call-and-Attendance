document.addEventListener('DOMContentLoaded', function() {
  const el = id => document.getElementById(id);
  const materia = el('materia-select'), turma = el('turma-select'), aula = el('aula-select');
  let groups = [], lessons = [];
  let sessionId = null, resultsId = null, countdown = null, resultsTimer = null, qrRetryTimer = null;
  let generation = 0, renderingResults = '', resultVersion = 0;
  let starting = false, ending = null, qrRequest = null;
  const notify = (message, kind) => window.UI ? UI.notify(message, kind) : alert(message);

  function options(select, rows, placeholder, label, selected) {
    select.replaceChildren();
    const first = document.createElement('option'); first.value = ''; first.textContent = placeholder; select.appendChild(first);
    for (const row of rows) { const option = document.createElement('option'); option.value = row.id; option.textContent = label(row); select.appendChild(option); }
    select.value = selected != null && rows.some(row => String(row.id) === String(selected)) ? String(selected) : '';
  }
  async function loadSubjects() {
    const rows = await Aura.json('/api/materias/');
    options(materia, rows, rows.length ? 'Selecione uma matéria' : 'Nenhuma matéria vinculada a este professor', row => `${row.nome} (${row.codigo})`, materia.value);
  }
  function resetCall() {
    // Descarta requisições pendentes, inclusive da mesma sessão retomada
    // depois de selecionar outra aula.
    generation++; resultVersion++; starting = false; ending = null; qrRequest = null;
    clearInterval(countdown); clearTimeout(resultsTimer); clearTimeout(qrRetryTimer); sessionId = null; resultsId = null; renderingResults = '';
    el('qr-code-container').style.display = 'none'; el('qr-code-img').removeAttribute('src');
    el('attendance-results').hidden = true; el('attendance-list').replaceChildren();
    el('start-session-btn').disabled = false; el('end-session-btn').hidden = true; el('refresh-results-btn').hidden = true;
    el('start-session-btn').textContent = 'Iniciar chamada'; el('end-session-btn').disabled = false;
    el('call-state').textContent = 'Aguardando início';
  }
  async function subjectChanged() {
    resetCall(); const version = generation;
    el('aulas-section').style.display = 'none'; el('session-section').style.display = 'none';
    el('turmas-section').style.display = materia.value ? 'grid' : 'none';
    options(turma, [], 'Carregando turmas…', row => row.nome); options(aula, [], 'Selecione uma aula', row => row.titulo);
    if (!materia.value) return;
    turma.disabled = true;
    try {
      const rows = await Aura.json(`/api/turmas/?materia=${materia.value}`);
      if (version !== generation) return;
      groups = rows; options(turma, rows, rows.length ? 'Selecione uma turma' : 'Nenhuma turma cadastrada nesta matéria', row => `${row.nome} (${row.semestre}/${row.ano})`);
    } catch(error) { if (version === generation) { options(turma, [], 'Não foi possível carregar. Selecione a matéria novamente.', row => row.nome); notify(error.message,'error'); } }
    finally { if (version === generation) turma.disabled = false; }
  }
  async function groupChanged() {
    resetCall(); const version = generation;
    el('session-section').style.display = 'none'; el('aulas-section').style.display = turma.value ? 'grid' : 'none';
    el('invite-code').value = groups.find(row => String(row.id) === turma.value)?.codigo_acesso || '';
    options(aula, [], 'Carregando aulas…', row => row.titulo);
    if (!turma.value) return;
    aula.disabled = true;
    try {
      const rows = await Aura.json(`/api/aulas/?turma=${turma.value}`);
      if (version !== generation) return;
      lessons = rows; options(aula, rows, rows.length ? 'Selecione uma aula' : 'Nenhuma aula cadastrada nesta turma', row => `${row.titulo} (${new Date(row.data + 'T12:00:00').toLocaleDateString('pt-BR')})`);
    } catch(error) { if (version === generation) { options(aula, [], 'Não foi possível carregar. Selecione a turma novamente.', row => row.titulo); notify(error.message,'error'); } }
    finally { if (version === generation) aula.disabled = false; }
  }
  function lessonChanged() {
    resetCall(); el('session-section').style.display = aula.value ? 'block' : 'none';
    const lesson = lessons.find(row => String(row.id) === aula.value);
    if (lesson) el('call-title').textContent = `${lesson.titulo} · ${lesson.hora_inicio.slice(0,5)}–${lesson.hora_fim.slice(0,5)}`;
  }
  materia.addEventListener('change', subjectChanged); turma.addEventListener('change', groupChanged); aula.addEventListener('change', lessonChanged);

  function showQR(data, elapsed) {
    el('qr-code-img').src = data.qr_image;
    el('qr-code-container').style.display = 'block';
    clearInterval(countdown);
    // Usa o relógio do servidor e desconta a requisição inteira por segurança.
    const remaining = Math.max(0, new Date(data.token_expira_em) - new Date(data.servidor_agora) - elapsed);
    const expires = performance.now() + remaining;
    const tick = () => {
      const seconds = Math.max(0, Math.ceil((expires - performance.now()) / 1000));
      el('countdown').textContent = `${String(Math.floor(seconds / 60)).padStart(2,'0')}:${String(seconds % 60).padStart(2,'0')}`;
      if (seconds === 0) {
        clearInterval(countdown); el('qr-code-img').removeAttribute('src');
        qrRetryTimer = setTimeout(refreshQR, 250);
      }
    };
    countdown = setInterval(tick, 1000); tick();
  }
  async function refreshQR() {
    const requested = sessionId;
    if (!requested || ending || qrRequest) return;
    const request = { id: requested, generation }; qrRequest = request;
    const current = () => request.generation === generation && requested === sessionId && !ending;
    clearInterval(countdown); clearTimeout(qrRetryTimer);
    el('qr-code-img').removeAttribute('src');
    el('countdown').textContent = 'Atualizando…';
    const started = performance.now();
    try {
      const data = await Aura.json(`/api/sessoes/${requested}/token/?origin=${encodeURIComponent(window.location.origin)}`);
      if (current()) {
        if (!data.qr_image?.startsWith('data:image/svg+xml;base64,') ||
            !Number.isFinite(Date.parse(data.token_expira_em)) || !Number.isFinite(Date.parse(data.servidor_agora))) {
          throw new Error('Não foi possível carregar o QR Code.');
        }
        qrRequest = null; showQR(data, performance.now() - started);
      }
    } catch(error) {
      if (current()) {
        el('countdown').textContent = 'Tentando atualizar…'; notify(error.message,'error');
        qrRetryTimer = setTimeout(refreshQR, 3000);
      }
    }
    finally { if (qrRequest === request) qrRequest = null; }
  }
  function showClosedCall(id) {
    resetCall(); resultsId = id;
    el('attendance-results').hidden = false; el('refresh-results-btn').hidden = false;
    el('call-state').textContent = 'Chamada encerrada';
    window.dispatchEvent(new Event('aura:changed'));
  }
  async function loadResults(id) {
    const version = ++resultVersion;
    clearTimeout(resultsTimer);
    try {
      const data = await Aura.json(`/api/sessoes/${id}/resultados/`);
      if (id !== resultsId || version !== resultVersion) return;
      if (data.ativa === false && id === sessionId) showClosedCall(id);
      const signature = JSON.stringify(data.resultados);
      if (signature !== renderingResults) {
        renderingResults = signature; el('attendance-list').replaceChildren();
        for (const result of data.resultados) {
          const item = document.createElement('li');
          item.textContent = `${result.aluno} - ${result.status === 'presente' ? 'Presente' : 'Falta'}`;
          if (result.horario) { const time = document.createElement('small'); time.style.display = 'block'; time.textContent = new Date(result.horario).toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'}) + (result.status === 'falta' ? ' · Fora do raio' : ' · Localização validada'); item.appendChild(time); }
          el('attendance-list').appendChild(item);
        }
      }
      el('count-present').textContent = data.resultados.filter(row => row.status === 'presente').length;
      el('count-absent').textContent = data.resultados.filter(row => row.status === 'falta').length;
      el('count-pending').textContent = data.aguardando ?? '—';
      el('attendance-status').textContent = data.resultados.length ? (sessionId ? 'Atualização automática a cada 5 segundos.' : 'Chamada encerrada. Registros finais.') : 'Nenhum aluno verificou a presença ainda.';
    } catch(error) { if (id === resultsId && version === resultVersion) el('attendance-status').textContent = 'Não foi possível atualizar. Use Atualizar registros para tentar novamente.'; }
    finally { if (id === sessionId && version === resultVersion) resultsTimer = setTimeout(() => loadResults(id),5000); }
  }
  el('start-session-btn').addEventListener('click', async function() {
    if (!aula.value || sessionId || starting) return;
    const version = generation;
    const button = el('start-session-btn'); starting = true;
    button.disabled = true; button.textContent = 'Iniciando…';
    try {
      const data = await Aura.json('/api/sessoes/', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({aula:aula.value})});
      if (version !== generation) { notify('Chamada iniciada. Selecione novamente a aula e clique em Iniciar chamada para retomá-la.'); return; }
      sessionId = data.id; resultsId = data.id;
      el('end-session-btn').hidden = false; el('refresh-results-btn').hidden = false; el('attendance-results').hidden = false;
      el('call-state').textContent = 'Chamada aberta';
      el('location-info').textContent = `Localização institucional · Raio permitido de ${data.professor_radius_meters} m`;
      el('qr-code-container').style.display = 'block';
      refreshQR(); loadResults(data.id);
      window.dispatchEvent(new Event('aura:changed'));
    } catch(error) { if (version === generation) notify(error.message, 'error'); }
    finally { if (version === generation) { starting = false; button.disabled = Boolean(sessionId); button.textContent = 'Iniciar chamada'; } }
  });
  el('end-session-btn').addEventListener('click', async function() {
    if (!sessionId || ending) return;
    const request = { id: sessionId, generation }; ending = request;
    const current = () => request.generation === generation && request.id === sessionId;
    el('end-session-btn').disabled = true; clearInterval(countdown); clearTimeout(qrRetryTimer);
    el('qr-code-img').removeAttribute('src');
    try {
      await Aura.json(`/api/sessoes/${request.id}/encerrar/`,{method:'POST'});
      if (!current()) return;
      showClosedCall(request.id); loadResults(request.id); notify('Chamada encerrada.');
    } catch(error) {
      if (current()) {
        notify(error.message,'error'); ending = null;
        // Outra tela pode ter encerrado a chamada. Consulta o estado atual
        // antes de retomar o contador do QR.
        await loadResults(request.id);
        if (current()) refreshQR();
      }
    } finally { if (ending === request) ending = null; if (current()) el('end-session-btn').disabled = false; }
  });
  el('refresh-results-btn').addEventListener('click', () => { if (resultsId) loadResults(resultsId); if (sessionId) { clearInterval(countdown); refreshQR(); } });
  el('projector-btn').addEventListener('click', function() { const enabled = document.body.classList.toggle('projector'); this.setAttribute('aria-pressed',String(enabled)); this.textContent = enabled ? 'Sair do modo projetor' : 'Modo projetor'; });
  el('copy-code').addEventListener('click', async () => { try { await navigator.clipboard.writeText(el('invite-code').value); notify('Código copiado.'); } catch { el('invite-code').select(); notify('Selecione e copie o código exibido.'); } });
  el('qr-code-img').addEventListener('error', () => notify('Não foi possível carregar o QR Code. Confira a conexão e clique em Atualizar registros.','error'));
  el('local-origin-warning').hidden = !['localhost','127.0.0.1'].includes(window.location.hostname);
  window.AuraCall = {
    async select(subjectId, groupId, lessonId) {
      location.hash = 'chamada'; await loadSubjects(); materia.value = String(subjectId); await subjectChanged();
      if (groupId) { turma.value = String(groupId); await groupChanged(); }
      if (lessonId) { aula.value = String(lessonId); lessonChanged(); }
    },
    reload: loadSubjects,
  };
  loadSubjects().catch(error => notify(error.message,'error')).finally(() => {
    el('loading').style.display = 'none'; el('content').style.display = 'block';
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && sessionId) refreshQR(); });
  window.addEventListener('beforeunload', () => { generation++; resultVersion++; clearInterval(countdown); clearTimeout(resultsTimer); clearTimeout(qrRetryTimer); sessionId = null; resultsId = null; });
});
