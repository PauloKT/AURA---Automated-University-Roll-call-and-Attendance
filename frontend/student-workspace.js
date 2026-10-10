document.addEventListener('DOMContentLoaded',()=>{
  const e=UI.escape;
  async function load(){
    try{
      const data=await Aura.json('/api/interface/painel/');
      const total=data.frequencias.reduce((n,row)=>n+row.aulas,0),present=data.frequencias.reduce((n,row)=>n+row.presencas,0);
      document.getElementById('student-stats').innerHTML=[[data.turmas.length,'Turmas'],[total?UI.percent(present/total*100):'Sem dados','Frequência geral'],[present,'Presenças'],[data.frequencias.filter(row=>row.situacao==='reprovado').length,'Matérias em atenção']].map(([value,label])=>`<div class="stat"><strong>${e(value)}</strong><span>${e(label)}</span></div>`).join('');
      const rows=data.frequencias;
      const overview=rows.map(row=>`<div class="activity-row"><div><p>${e(row.materia)}</p><small>${e(row.turma)} · ${row.aulas?UI.percent(row.percentual):'Sem chamadas'}</small><progress max="100" value="${row.percentual}" aria-label="Frequência em ${e(row.materia)}"></progress></div>${UI.badge(row.situacao)}</div>`).join('');
      document.getElementById('student-overview').innerHTML=overview||UI.empty('Você ainda não está em uma turma','Peça o código ao professor para começar.','<a class="button" href="#entrar">Entrar em uma turma</a>');
      document.getElementById('student-report').innerHTML=rows.length?UI.frequencyTable(rows, true):UI.empty('Ainda sem frequência para acompanhar','Entre em uma turma para ver seus registros.');
      document.getElementById('student-activity').innerHTML=data.recentes.map(row=>`<div class="activity-row"><div><p>${e(row.aula)}</p><small>${e(row.turma)} · ${UI.date(row.data)}</small></div>${UI.badge(row.status)}</div>`).join('')||UI.empty('Nenhum registro ainda','Sua presença ou falta aparecerá aqui após a verificação.');
    }catch(error){document.getElementById('student-overview').innerHTML=UI.empty('Não foi possível atualizar',error.message,'<button class="button secondary" id="student-retry">Tentar novamente</button>');document.getElementById('student-retry').addEventListener('click',load);}
  }
  window.addEventListener('aura:joined',load);
  window.addEventListener('pageshow',load);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});
  load();
});
