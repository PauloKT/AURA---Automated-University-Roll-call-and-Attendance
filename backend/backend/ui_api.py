"""Dados dos painéis; frequência calculada apenas sobre chamadas encerradas."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.frequency import consultar_frequencias
from attendance.models import Presenca, SessaoChamada
from courses.models import Aula, Materia, Turma


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
        frequencies = consultar_frequencias(ids, aluno_id=user.pk if user.role == 'aluno' else None)
        records = Presenca.objects.filter(sessao__aula__turma_id__in=ids)
        if user.role == 'aluno':
            records = records.filter(aluno=user)
        group_map = {group.pk: group for group in groups}
        reports = []
        for frequency in frequencies.vinculos:
            enrollment = frequency.vinculo
            group = group_map[enrollment.turma_id]
            reports.append({
                'vinculo_id': enrollment.pk, 'aluno_id': enrollment.aluno_id,
                'aluno': enrollment.aluno.get_full_name() or enrollment.aluno.username,
                'matricula': enrollment.aluno.matricula or '', 'turma_id': group.pk,
                'turma': group.nome, 'materia_id': group.materia_id, 'materia': group.materia.nome,
                'aulas': frequency.chamadas, 'presencas': frequency.presencas, 'faltas': frequency.faltas,
                'percentual': frequency.percentual, 'situacao': frequency.situacao,
                'minimo': group.materia.frequencia_minima,
            })
        result_groups = []
        for group in groups:
            summary = frequencies.turmas[group.pk]
            result_groups.append({
                'id': group.pk, 'nome': group.nome, 'materia': group.materia_id,
                'materia_nome': group.materia.nome, 'professor': group.materia.professor.get_full_name() or group.materia.professor.username,
                'semestre': group.semestre, 'ano': group.ano, 'ativa': group.ativa,
                'codigo_acesso': group.codigo_acesso if user.role == 'professor' else None,
                'alunos': summary.alunos, 'chamadas': summary.chamadas,
                'media': summary.media,
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
