document.addEventListener('DOMContentLoaded', () => {
  const $ = id => document.getElementById(id), e = UI.escape;
  let data = {materias:[],turmas:[],aulas:[],frequencias:[],recentes:[]};
  let editing = {}, currentTab = 'geral', removing = null, requestVersion = 0;
  const stats = rows => rows.map(([number,label]) => `<div class="stat"><strong>${e(number)}</strong><span>${e(label)}</span></div>`).join('');
  const actionIcons = { 'edit-subject':'edit', 'edit-group':'edit', 'edit-lesson':'edit', 'delete-subject':'trash', 'delete-group':'trash', 'delete-lesson':'trash', 'remove-student':'users', 'call':'qr', 'export-group':'download', 'subject-detail':'book' };
  const action = (type,id,label,kind='secondary') => `<button class="button ${kind} small" data-${type}="${e(id)}">${actionIcons[type] ? UI.icon(actionIcons[type]) : ''}${e(label)}</button>`;
  const groupById = id => data.turmas.find(group => String(group.id) === String(id));
  const selectedGroup = () => groupById(location.hash.split('/')[1]);
  function frequencyTable(rows) {
    if (!rows.length) return UI.empty('Nenhum registro para exibir','Os alunos aparecem aqui depois de entrar na turma.');
    return UI.frequencyTable(rows);
  }
  function lessonRows(rows) {
    if (!rows.length) return UI.empty('Nenhuma aula cadastrada','Crie uma aula para preparar a próxima chamada.', '<button class="button secondary" data-new="aula">Criar aula</button>');
    return rows.map(row => { const group = groupById(row.turma_id); const date = new Date(row.data+'T12:00:00'); return `<div class="lesson-row"><div class="lesson-date"><strong>${date.getDate()}</strong>${e(date.toLocaleDateString('pt-BR',{month:'short'}))}</div><div class="lesson-copy"><strong>${e(row.titulo)}</strong><small>${e(group?.nome)} · ${e(row.horario_inicio.slice(0,5))}–${e(row.horario_fim.slice(0,5))}</small></div>${action('call',row.id,'Abrir chamada')}</div>`; }).join('');
  }
  function renderSubjects() {
    const query = $('subject-search').value.toLowerCase();
    const rows = data.materias.filter(row => `${row.nome} ${row.codigo}`.toLowerCase().includes(query));
    $('subject-list').innerHTML = rows.map(row => `<article class="course-card"><span class="course-code">${e(row.codigo)}</span><h3>${e(row.nome)}</h3><p class="muted">${row.carga_horaria} horas · Frequência mínima ${row.frequencia_minima}%</p><div class="card-meta"><span>${data.turmas.filter(group=>group.materia===row.id).length} turmas</span></div><div class="actions">${action('subject-detail',row.id,'Ver detalhes')}${action('edit-subject',row.id,'Editar')}${action('delete-subject',row.id,'Excluir','danger')}</div></article>`).join('') || UI.empty('Nenhuma matéria encontrada',query ? 'Tente outro nome ou código.' : 'Cadastre a primeira matéria para organizar suas turmas.', '<button class="button" data-new="materia">Criar matéria</button>');
  }
  function renderGroups() {
    const query = $('group-search').value.toLowerCase();
    const rows = data.turmas.filter(row => `${row.nome} ${row.materia_nome}`.toLowerCase().includes(query));
    $('group-list').innerHTML = rows.map(row => `<article class="course-card"><span class="course-code">${e(row.materia_nome)}</span><h3>${e(row.nome)}</h3><p class="muted">${e(row.professor)}<br>${e(row.semestre)} / ${row.ano} ${row.ativa ? '' : '· Inativa'}</p><div class="card-meta"><span>${row.alunos} alunos</span><span>${row.chamadas} chamadas</span></div><p>Frequência média <strong>${UI.percent(row.media)}</strong></p><div class="actions"><a class="button small" href="#detalhe/${row.id}">Visualizar turma</a>${action('edit-group',row.id,'Editar')}</div></article>`).join('') || UI.empty('Nenhuma turma encontrada', query ? 'Tente outro nome.' : 'Crie uma turma e compartilhe o código com os alunos.', '<button class="button" data-new="turma">Criar turma</button>');
  }
  function reportRows() {
    return data.frequencias.filter(row => (!$('report-group').value || String(row.turma_id)===$('report-group').value) && row.aluno.toLowerCase().includes($('report-student').value.toLowerCase()) && (!$('report-status').value || row.situacao===$('report-status').value));
  }
  function renderReport() { $('report-table').innerHTML = frequencyTable(reportRows()); }
  function renderDetail() {
    const group = selectedGroup();
    if (!group) { $('group-detail-body').innerHTML = UI.empty('Turma não encontrada','Selecione uma turma na lista.'); return; }
    $('group-title').textContent = group.nome; $('group-subtitle').textContent = `${group.materia_nome} · ${group.semestre}/${group.ano}`;
    document.querySelectorAll('[data-tab]').forEach(tab => { tab.setAttribute('aria-selected',String(tab.dataset.tab === currentTab)); tab.tabIndex = tab.dataset.tab === currentTab ? 0 : -1; });
    $('group-detail-body').setAttribute('aria-labelledby',`tab-${currentTab}`);
    const rows = data.frequencias.filter(row=>row.turma_id===group.id);
    if (currentTab==='geral') $('group-detail-body').innerHTML = `<div class="stats">${stats([[group.alunos,'Alunos matriculados'],[group.chamadas,'Chamadas'],[UI.percent(group.media),'Frequência média'],[rows.filter(row=>row.situacao==='reprovado').length,'Alunos em atenção']])}</div><div class="split-layout"><div class="panel"><h2>Próximos encontros e aulas recentes</h2>${lessonRows(data.aulas.filter(row=>row.turma_id===group.id).slice(0,5))}</div><div class="panel"><h2>Código da turma</h2><p class="muted">Compartilhe com os alunos para entrar nesta turma.</p><div class="code-display">${e(group.codigo_acesso)}</div><hr class="panel-divider"><dl class="detail-list"><dt>Professor</dt><dd>${e(group.professor)}</dd><dt>Situação</dt><dd>${group.ativa?'Ativa':'Inativa'}</dd></dl><div class="form-actions">${action('delete-group',group.id,'Excluir turma','danger')}</div></div></div>`;
    else if (currentTab==='alunos') $('group-detail-body').innerHTML = `<div class="panel"><h2>Alunos matriculados</h2><p class="muted">Para adicionar alunos, compartilhe o código ${e(group.codigo_acesso)}.</p>${rows.length ? `<div class="table-wrap report-wrap" tabindex="0" role="region" aria-label="Alunos matriculados"><table class="responsive-table roster-table" role="table"><thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Aluno</th><th scope="col" role="columnheader">Matrícula</th><th scope="col" role="columnheader">Ação</th></tr></thead><tbody role="rowgroup">${rows.map(row=>`<tr role="row"><td class="report-name" role="cell">${e(row.aluno)}</td><td role="cell"><span class="mobile-label" aria-hidden="true">Matrícula</span>${e(row.matricula||'Não informada')}</td><td role="cell">${action('remove-student',row.vinculo_id,'Remover da turma','danger')}</td></tr>`).join('')}</tbody></table></div>` : UI.empty('A turma ainda não tem alunos','Mostre o código da turma para que eles possam entrar.')}</div>`;
    else if (currentTab==='aulas') { const lessons=data.aulas.filter(row=>row.turma_id===group.id); $('group-detail-body').innerHTML = `<div class="panel"><header class="panel-header"><h2>Aulas</h2><button class="button" data-new="aula">Criar aula</button></header>${lessons.map(row=>`<div class="lesson-row"><div class="lesson-copy"><strong>${e(row.titulo)}</strong><small>${UI.date(row.data)} · ${e(row.horario_inicio.slice(0,5))}–${e(row.horario_fim.slice(0,5))}</small></div><div class="actions">${action('call',row.id,'Chamada')}${action('edit-lesson',row.id,'Editar')}${action('delete-lesson',row.id,'Excluir','danger')}</div></div>`).join('') || UI.empty('Nenhuma aula cadastrada','Use Criar aula para agendar um encontro.')}</div>`; }
    else $('group-detail-body').innerHTML = `<div class="panel"><header class="panel-header"><h2>${currentTab==='relatorios'?'Relatório da turma':'Frequência dos alunos'}</h2>${currentTab==='relatorios'?action('export-group',group.id,'Exportar CSV'):''}</header>${frequencyTable(rows)}</div>`;
  }
  async function load() {
    const version=++requestVersion;
    try {
      const fresh=await Aura.json('/api/interface/painel/'); if(version!==requestVersion)return; data=fresh;
      const students=new Set(data.frequencias.map(row=>row.aluno_id));
      const risk=new Set(data.frequencias.filter(row=>row.situacao==='reprovado').map(row=>row.aluno_id));
      $('dashboard-stats').innerHTML=stats([[data.turmas.length,'Turmas'],[students.size,'Alunos'],[data.frequencias.reduce((n,row)=>n+row.presencas,0),'Presenças registradas'],[risk.size,'Alunos em atenção']]);
      const today = new Date(); today.setHours(0,0,0,0);
      const upcoming=data.aulas.filter(row=>new Date(row.data+'T23:59:59')>=today).sort((a,b)=>(a.data+a.horario_inicio).localeCompare(b.data+b.horario_inicio));
      $('dashboard-lessons').innerHTML=lessonRows((upcoming.length?upcoming:data.aulas).slice(0,5));
      $('dashboard-groups').innerHTML=data.turmas.slice(0,4).map(row=>`<div class="activity-row"><div><a href="#detalhe/${row.id}">${e(row.nome)}</a><small>${e(row.materia_nome)} · ${row.alunos} alunos</small></div><strong>${UI.percent(row.media)}</strong></div>`).join('') || UI.empty('Sua primeira turma começa aqui','Crie uma turma e convide seus alunos.','<button class="button" data-new="turma">Criar turma</button>');
      $('dashboard-activity').innerHTML=data.recentes.slice(0,5).map(row=>`<div class="activity-row"><div><p>${e(row.aluno)}</p><small>${e(row.aula)} · ${UI.date(row.data)}</small></div>${UI.badge(row.status)}</div>`).join('') || UI.empty('Ainda sem registros','Os resultados aparecerão quando os alunos verificarem a presença.');
      const groupFilter=$('report-group').value; $('report-group').innerHTML='<option value="">Todas as turmas</option>'+data.turmas.map(row=>`<option value="${row.id}">${e(row.nome)} — ${e(row.materia_nome)}</option>`).join(''); $('report-group').value=groupFilter;
      renderSubjects();renderGroups();renderReport();renderDetail();
    } catch(error) {
      UI.notify(error.message,'error');
      const message=UI.empty('Não foi possível carregar os dados','Confira sua conexão e tente novamente.','<button class="button" data-reload>Tentar novamente</button>');
      for(const id of ['dashboard-lessons','subject-list','group-list','report-table','group-detail-body']) $(id).innerHTML=message;
    }
  }
  function openForm(type,id) {
    const collection={materia:'materias',turma:'turmas',aula:'aulas'}[type];
    const row=data[collection].find(row=>row.id===Number(id)); editing[type]=row?.id;
    if(type==='turma' && !data.materias.length){UI.notify('Crie uma matéria antes de cadastrar a turma.');openForm('materia');return;}
    if(type==='aula' && !data.turmas.length){UI.notify('Crie uma turma antes de cadastrar a aula.');openForm('turma');return;}
    $(`${type}-form`).reset();$(`${type}-error`).textContent='';$(`${type}-dialog-title`).textContent=`${row?'Editar':'Criar'} ${type==='materia'?'matéria':type}`;
    if(type==='materia') { $('materia-nome').value=row?.nome||'';$('materia-codigo').value=row?.codigo||'';$('materia-carga').value=row?.carga_horaria||'';$('materia-freq').value=row?.frequencia_minima??75; }
    if(type==='turma') { $('turma-materia').innerHTML=data.materias.map(row=>`<option value="${row.id}">${e(row.nome)}</option>`).join('');$('turma-materia').value=row?.materia||$('materia-select').value||data.materias[0].id;$('turma-nome').value=row?.nome||'';$('turma-semestre').value=row?.semestre||'';$('turma-ano').value=row?.ano||new Date().getFullYear(); }
    if(type==='aula') { $('aula-turma').innerHTML=data.turmas.map(row=>`<option value="${row.id}">${e(row.materia_nome)} — ${e(row.nome)}</option>`).join('');$('aula-turma').value=row?.turma_id||selectedGroup()?.id||$('turma-select').value||data.turmas[0].id;$('aula-titulo').value=row?.titulo||'';$('aula-data').value=row?.data||new Date().toLocaleDateString('en-CA');$('aula-inicio').value=row?.horario_inicio||'';$('aula-fim').value=row?.horario_fim||''; }
    $(`${type}-dialog`).showModal();
  }
  for(const type of ['materia','turma','aula']) $(`${type}-form`).addEventListener('submit',async event=>{
    event.preventDefault();const button=$(`create-${type}-btn`);button.disabled=true;$(`${type}-error`).textContent='';
    const id=editing[type];const endpoint={materia:'materias',turma:'turmas',aula:'aulas'}[type];
    const payload=type==='materia'?{nome:$('materia-nome').value.trim(),codigo:$('materia-codigo').value.trim(),carga_horaria:Number($('materia-carga').value),frequencia_minima:Number($('materia-freq').value)}:type==='turma'?{nome:$('turma-nome').value.trim(),materia:Number($('turma-materia').value),semestre:$('turma-semestre').value.trim(),ano:Number($('turma-ano').value)}:{turma:Number($('aula-turma').value),titulo:$('aula-titulo').value.trim(),data:$('aula-data').value,hora_inicio:$('aula-inicio').value,hora_fim:$('aula-fim').value};
    try {const saved=await Aura.json(`/api/${endpoint}/${id?id+'/':''}`,{method:id?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});$(`${type}-dialog`).close();UI.notify(`${type==='materia'?'Matéria':type==='turma'?'Turma':'Aula'} ${id?'atualizada':'criada'} com sucesso.`);await load();await window.AuraCall.reload();if(!id&&type==='aula'){const group=groupById(saved.turma);await window.AuraCall.select(group.materia,group.id,saved.id);}else if(!id&&type==='turma'){location.hash=`detalhe/${saved.id}`;} }
    catch(error){$(`${type}-error`).textContent=error.message;}finally{button.disabled=false;}
  });
  function confirmDelete(endpoint,id,description){removing={endpoint,id};$('confirm-description').textContent=description;$('confirm-error').textContent='';$('confirm-dialog').showModal();}
  $('confirm-delete').addEventListener('click',async function(){if(!removing)return;this.disabled=true;try{await Aura.json(`/api/${removing.endpoint}/${removing.id}/`,{method:'DELETE'});$('confirm-dialog').close();UI.notify('Registro excluído.');await load();await window.AuraCall.reload();}catch(error){$('confirm-error').textContent=error.message;}finally{this.disabled=false;}});
  function exportRows(rows){const headers=['Aluno','Turma','Matéria','Chamadas','Presenças','Faltas','Frequência (%)'];const cell=value=>'"'+String(value??'').replace(/^[=+@-]/,"'$&").replace(/"/g,'""')+'"';const csv='\ufeff'+[headers,...rows.map(row=>[row.aluno,row.turma,row.materia,row.aulas,row.presencas,row.faltas,row.percentual])].map(row=>row.map(cell).join(';')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='frequencia-aura.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  document.addEventListener('click',async event=>{
    const target=event.target.closest('button');if(!target)return;const d=target.dataset;
    try {
      if(d.new)openForm(d.new);if(d.editSubject)openForm('materia',d.editSubject);if(d.editGroup)openForm('turma',d.editGroup);if(d.editLesson)openForm('aula',d.editLesson);
      if(d.deleteSubject)confirmDelete('materias',d.deleteSubject,'Excluir esta matéria também exclui suas turmas, aulas e registros de chamada. Esta ação não pode ser desfeita.');
      if(d.deleteGroup)confirmDelete('turmas',d.deleteGroup,'Excluir esta turma também exclui suas aulas, matrículas e registros de chamada. Esta ação não pode ser desfeita.');
      if(d.deleteLesson)confirmDelete('aulas',d.deleteLesson,'Excluir esta aula também exclui suas chamadas e registros. Esta ação não pode ser desfeita.');
      if(d.removeStudent)confirmDelete('turma-aluno',d.removeStudent,'Remover o aluno desta turma? Os registros já realizados serão preservados.');
      if(d.call){const lesson=data.aulas.find(row=>row.id===Number(d.call));const group=groupById(lesson.turma_id);await window.AuraCall.select(group.materia,group.id,lesson.id);}
      if(d.tab){currentTab=d.tab;renderDetail();}
      if(d.subjectDetail){const subject=data.materias.find(row=>row.id===Number(d.subjectDetail));$('group-search').value=subject.nome;renderGroups();location.hash='turmas';}
      if(d.exportGroup)exportRows(data.frequencias.filter(row=>row.turma_id===Number(d.exportGroup)));
      if(target.hasAttribute('data-reload'))load();
    }catch(error){UI.notify(error.message,'error');}
  });
  document.querySelector('.tabs').addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll('[data-tab]')];const index=tabs.indexOf(document.activeElement);const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next].click();tabs[next].focus();});
  $('edit-current-group').addEventListener('click',()=>{if(selectedGroup())openForm('turma',selectedGroup().id);});
  $('call-current-group').addEventListener('click',()=>{const group=selectedGroup();if(group)window.AuraCall.select(group.materia,group.id).catch(error=>UI.notify(error.message,'error'));});
  $('subject-search').addEventListener('input',renderSubjects);$('group-search').addEventListener('input',renderGroups);
  for(const id of ['report-group','report-student','report-status'])$(id).addEventListener('input',renderReport);
  $('export-report').addEventListener('click',()=>exportRows(reportRows()));
  window.addEventListener('hashchange',()=>{currentTab='geral';renderDetail();});
  window.addEventListener('aura:changed',load);
  load();
});
