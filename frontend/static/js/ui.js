window.UI = (() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const icon = name => `<svg class="icon" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="${escape(document.body.dataset.iconsUrl || '/static/images/icons.svg?v=aura-icons-1')}#${escape(name)}"></use></svg>`;
  function notify(message, kind = 'info') {
    const region = document.getElementById('toast-region');
    if (!region) return;
    const toast = document.createElement('div');
    toast.className = 'toast'; toast.dataset.kind = kind; toast.textContent = message;
    region.appendChild(toast); setTimeout(() => toast.remove(), 6500);
  }
  const date = value => value ? new Date(value.length === 10 ? value + 'T12:00:00' : value).toLocaleDateString('pt-BR') : '—';
  const percent = value => value == null ? 'Sem dados' : Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + '%';
  function frequencyTable(rows, student = false) {
    const label = student ? 'Minha frequência' : 'Frequência dos alunos';
    const firstColumn = student ? 'Matéria / turma' : 'Aluno / turma';
    const cell = (title, value, style = '') => `<td role="cell" class="${style}"><span class="mobile-label" aria-hidden="true">${title}</span><div>${value}</div></td>`;
    return `<div class="table-wrap report-wrap" role="region" aria-label="${label}" tabindex="0"><table class="responsive-table" role="table"><thead role="rowgroup"><tr role="row">${[firstColumn, 'Chamadas', 'Presenças', 'Faltas', 'Frequência', 'Situação'].map(title => `<th scope="col" role="columnheader">${title}</th>`).join('')}</tr></thead><tbody role="rowgroup">${rows.map(row => {
      const name = student ? row.materia : row.aluno;
      return `<tr role="row"><td class="report-name" role="cell">${escape(name)}<small>${escape(row.turma)}</small></td>${cell('Chamadas', escape(row.aulas))}${cell('Presenças', escape(row.presencas))}${cell('Faltas', escape(row.faltas))}${cell('Frequência', `${row.aulas ? percent(row.percentual) : 'Sem dados'}<progress max="100" value="${Number(row.percentual) || 0}" aria-label="Frequência de ${escape(name)}"></progress><small>Mínimo ${escape(row.minimo)}%</small>`, 'report-frequency')}${cell('Situação', badge(row.situacao), 'report-status')}</tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function badge(situation) {
    const options = { aprovado: ['good', 'Regular'], reprovado: ['warning', 'Atenção'], sem_dados: ['', 'Sem chamadas'], presente: ['good','Presente'], falta: ['bad','Falta'] };
    const [style, label] = options[situation] || ['', situation];
    return `<span class="badge ${style}">${escape(label)}</span>`;
  }
  const empty = (title, description = '', action = '') => `<div class="empty-state"><span class="empty-symbol" aria-hidden="true">${icon('inbox')}</span><h3>${escape(title)}</h3><p>${escape(description)}</p>${action}</div>`;
  function route(event) {
    const name = location.hash.slice(1).split('/')[0] || 'inicio';
    const panels = [...document.querySelectorAll('[data-panel]')];
    if (!panels.length) return;
    const actual = panels.some(panel => panel.dataset.panel === name) ? name : 'inicio';
    for (const panel of panels) panel.hidden = panel.dataset.panel !== actual;
    for (const link of document.querySelectorAll('[data-nav]')) {
      if (link.dataset.nav === actual || (actual === 'detalhe' && link.dataset.nav === 'turmas')) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
    const account = document.querySelector('.account-link');
    if (actual === 'perfil') account?.setAttribute('aria-current', 'page');
    else account?.removeAttribute('aria-current');
    if (event?.type === 'hashchange') {
      const heading = panels.find(panel => panel.dataset.panel === actual)?.querySelector('h1');
      if (heading) {
        heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
      }
      window.scrollTo({ top: 0, behavior: 'instant' });
    }
  }
  document.addEventListener('DOMContentLoaded', async () => {
    route(); window.addEventListener('hashchange', route);
    document.addEventListener('click', event => {
      if (event.target.closest('[data-close]')) event.target.closest('dialog')?.close();
    });
    const logoutButtons = [...document.querySelectorAll('[data-logout]')];
    let loggingOut = false;
    async function logout() {
      if (loggingOut) return;
      loggingOut = true;
      for (const button of logoutButtons) {
        button.disabled = true;
        button.setAttribute('aria-busy', 'true');
      }
      try {
        await Aura.json('/api/auth/logout/', { method: 'POST' });
        location.href = '/login.html';
      } catch (error) {
        loggingOut = false;
        for (const button of logoutButtons) {
          button.disabled = false;
          button.removeAttribute('aria-busy');
        }
        notify(error.message, 'error');
      }
    }
    for (const button of logoutButtons) button.addEventListener('click', logout);
    const today = document.getElementById('today-label');
    if (today) today.textContent = new Date().toLocaleDateString('pt-BR', { day:'numeric', month:'long', year:'numeric' });
    if (!document.body.dataset.role) return;
    try {
      const profile = await Aura.json('/api/interface/perfil/');
      if (profile.role !== document.body.dataset.role) { location.href = profile.role === 'professor' ? '/professor.html' : '/aluno.html'; return; }
      Profile.render(profile);
    } catch (error) {
      notify(error.message, 'error');
      const details = document.getElementById('profile-details');
      if (details) details.innerHTML = '<dt>Não foi possível carregar</dt><dd>Confira a conexão e atualize esta página.</dd>';
    }
  });
  return { escape, notify, date, percent, badge, empty, icon, frequencyTable };
})();
