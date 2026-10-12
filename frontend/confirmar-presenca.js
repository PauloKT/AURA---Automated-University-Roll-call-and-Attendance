document.addEventListener('DOMContentLoaded', async function() {
  const status = document.getElementById('flow-status');
  const error = document.getElementById('error-message');
  const success = document.getElementById('success-message');
  const retry = document.getElementById('confirm-btn');
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get('sessaoId');
  const token = params.get('token');
  let receipt = null;
  let busy = false;
  let done = false;


  function position() {
    return new Promise((resolve, reject) => {
      if (!window.isSecureContext) return reject(new Error('Abra o sistema pelo endereço HTTPS para permitir a localização no celular.'));
      if (!navigator.geolocation) return reject(new Error('Seu navegador não oferece localização.'));
      navigator.geolocation.getCurrentPosition(resolve, failure => {
        const messages = {
          1: 'Permita o acesso à localização nas configurações do navegador e tente novamente.',
          2: 'Localização indisponível. Ative a localização do celular e tente novamente.',
          3: 'Não conseguimos obter sua localização a tempo. Tente novamente.'
        };
        reject(new Error(messages[failure.code] || 'Não foi possível obter sua localização.'));
      }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 });
    });
  }

  async function confirm() {
    if (busy || done) return;
    busy = true;
    retry.disabled = true;
    retry.hidden = true;
    error.textContent = '';
    error.classList.remove('show');
    try {
      if (!/^\d+$/.test(sessionId || '') || !token) throw new Error('QR Code inválido. Leia o código exibido pelo professor.');
      if (!receipt) {
        status.textContent = 'Validando sua matrícula e o QR Code...';
        const data = await Aura.json(`/api/sessoes/${sessionId}/preparar/`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token })
        });
        receipt = data.comprovante;
        document.getElementById('lesson-info').textContent = `${data.turma} — ${data.aula}`;
      }
      status.textContent = 'Autorize a localização. Sua presença será confirmada automaticamente.';
      const location = await position();
      status.textContent = 'Validando localização e registrando presença...';
      const data = await Aura.json('/api/presenca/registrar/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessao_id: Number(sessionId), comprovante: receipt,
          latitude: location.coords.latitude, longitude: location.coords.longitude })
      });
      if (data.presenca?.valida !== true) {
        throw new Error(data.detail || 'Presença não confirmada. Confira sua localização e tente novamente.');
      }
      done = true;
      status.textContent = 'Processo concluído.';
      success.textContent = 'Presença confirmada com sucesso!';
      success.classList.add('show');
      document.getElementById('back-link').hidden = false;
    } catch (failure) {
      status.textContent = 'Presença ainda não confirmada.';
      error.textContent = failure.message;
      error.classList.add('show');
      retry.hidden = false;
      retry.disabled = false;
    } finally {
      busy = false;
    }
  }
  retry.addEventListener('click', confirm);
  await confirm();
});
