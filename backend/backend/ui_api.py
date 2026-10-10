"""Dados dos painéis; frequência calculada apenas sobre chamadas encerradas."""
from collections import Counter, defaultdict

from django.db.models import Count

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.views import frequency_result
from attendance.models import Presenca, SessaoChamada
from courses.models import Aula, Materia, Turma, TurmaAluno


class WorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == 'professor':
            groups = Turma.objects.filter(materia__professor=user)
            subjects = Materia.objects.filter(professor=user)
        elif user.role == 'aluno':
            groups = Turma.objects.filter(alunos__aluno=user)
            subjects = Materia.objects.filter(turmas__in=groups).distinct()
        else:
            return Response({'detail': 'Perfil sem acesso ao painel.'}, status=403)

        groups = list(groups.select_related('materia', 'materia__professor').order_by('nome'))
        ids = [group.pk for group in groups]
        lessons = list(Aula.objects.filter(turma_id__in=ids).order_by('-data', '-horario_inicio').values(
            'id', 'turma_id', 'titulo', 'data', 'horario_inicio', 'horario_fim'))
        sessions = list(SessaoChamada.objects.filter(aula__turma_id__in=ids).values(
            'id', 'aula_id', 'aula__turma_id', 'ativa'))
        totals = Counter(session['aula__turma_id'] for session in sessions if not session['ativa'])
        enrollments = TurmaAluno.objects.filter(turma_id__in=ids).select_related('aluno')
        records = Presenca.objects.filter(sessao__aula__turma_id__in=ids)
        if user.role == 'aluno':
            enrollments = enrollments.filter(aluno=user)
            records = records.filter(aluno=user)
        attended = {
            (row['sessao__aula__turma_id'], row['aluno_id']): row['total']
            for row in records.filter(valida=True, sessao__ativa=False).values('sessao__aula__turma_id', 'aluno_id').annotate(total=Count('id'))
        }
        group_map = {group.pk: group for group in groups}
        reports = []
        reports_by_group = defaultdict(list)
        for enrollment in enrollments:
            group = group_map[enrollment.turma_id]
            total = totals[group.pk]
            present = attended.get((group.pk, enrollment.aluno_id), 0)
            percentage, situation = frequency_result(total, present, group.materia.frequencia_minima)
            reports.append({
                'vinculo_id': enrollment.pk, 'aluno_id': enrollment.aluno_id,
                'aluno': enrollment.aluno.get_full_name() or enrollment.aluno.username,
                'matricula': enrollment.aluno.matricula or '', 'turma_id': group.pk,
                'turma': group.nome, 'materia_id': group.materia_id, 'materia': group.materia.nome,
                'aulas': total, 'presencas': present, 'faltas': total - present,
                'percentual': percentage, 'situacao': situation,
                'minimo': group.materia.frequencia_minima,
            })
            reports_by_group[group.pk].append(reports[-1])
        result_groups = []
        for group in groups:
            rows = reports_by_group[group.pk]
            result_groups.append({
                'id': group.pk, 'nome': group.nome, 'materia': group.materia_id,
                'materia_nome': group.materia.nome, 'professor': group.materia.professor.get_full_name() or group.materia.professor.username,
                'semestre': group.semestre, 'ano': group.ano, 'ativa': group.ativa,
                'codigo_acesso': group.codigo_acesso if user.role == 'professor' else None,
                'alunos': len(rows), 'chamadas': totals[group.pk],
                'media': round(sum(row['percentual'] for row in rows) / len(rows), 1) if rows and totals[group.pk] else None,
            })
        recent = [{
            'aluno': record.aluno.get_full_name() or record.aluno.username,
            'aula': record.sessao.aula.titulo, 'turma': record.sessao.aula.turma.nome,
            'data': record.registrada_em, 'status': 'presente' if record.valida else 'falta',
        } for record in records.select_related('aluno', 'sessao__aula__turma').order_by('-registrada_em')[:12]]
        return Response({
            'materias': list(subjects.order_by('nome').values('id', 'nome', 'codigo', 'carga_horaria', 'frequencia_minima')),
            'turmas': result_groups, 'aulas': lessons, 'sessoes': sessions,
            'frequencias': reports, 'recentes': recent,
        })
