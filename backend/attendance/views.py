from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core import signing
from rest_framework import serializers
from .models import SessaoChamada, Presenca
from .serializers import SessaoChamadaSerializer, SessaoTokenSerializer, PresencaSerializer, PresencaCreateSerializer
from courses.models import Aula, TurmaAluno
from django.shortcuts import get_object_or_404
from .geolocation import validate_coordinates, validate_radius
from .transactions import chamada_atomic, bloquear_sessao
from .qr import session_qr_image

class IsProfessor(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'professor'

class IsAluno(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'aluno'


class SessaoChamadaViewSet(viewsets.ModelViewSet):
    queryset = SessaoChamada.objects.all()
    serializer_class = SessaoChamadaSerializer
    permission_classes = [IsProfessor]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'professor':
            return (
                SessaoChamada.objects
                .filter(aula__turma__materia__professor=user)
                .select_related('aula', 'aula__turma', 'aula__turma__materia')
            )
        if user.role == 'aluno' and self.action in ('ativas', 'preparar'):
            return (
                SessaoChamada.objects
                .filter(aula__turma__alunos__aluno=user)
                .select_related('aula', 'aula__turma', 'aula__turma__materia')
            )
        return SessaoChamada.objects.none()

    def get_permissions(self):
        if self.action in ('ativas', 'preparar'):
            return [IsAluno()]
        return super().get_permissions()

    @action(detail=False, methods=['get'])
    def ativas(self, request):
        sessoes = self.get_queryset().filter(ativa=True).exclude(
            presencas__in=Presenca.objects.filter(aluno=request.user, valida=True),
        ).order_by('-iniciada_em')
        return Response({'chamadas': [{
            'id': sessao.id,
            'turma_id': sessao.aula.turma_id,
            'turma': sessao.aula.turma.nome,
            'materia': sessao.aula.turma.materia.nome,
            'aula': sessao.aula.titulo,
            'iniciada_em': sessao.iniciada_em,
        } for sessao in sessoes]})

    @action(detail=True, methods=['post'])
    def preparar(self, request, pk=None):
        sessao = self.get_object()
        token = serializers.CharField(max_length=100).run_validation(request.data.get('token'))
        with chamada_atomic():
            sessao = bloquear_sessao(sessao.pk)
            if not TurmaAluno.objects.select_for_update().filter(turma_id=sessao.aula.turma_id, aluno=request.user).only('id').first():
                raise ValidationError({'detail': 'Você não está matriculado nesta turma.'})
            if not sessao.is_token_valid() or token != sessao.token_atual:
                raise ValidationError({'detail': 'QR Code expirado ou chamada encerrada. Leia o QR Code atual.'})
            # Reserva dois minutos para obter o GPS após ler um QR válido.
            comprovante = signing.dumps(
                {'sessao': sessao.pk, 'aluno': request.user.pk}, salt='attendance.scan',
            )
        return Response({
            'comprovante': comprovante,
            'prazo_segundos': 120,
            'aula': sessao.aula.titulo,
            'turma': sessao.aula.turma.nome,
            'radius_meters': sessao.professor_radius_meters,
        }, headers={'Cache-Control': 'no-store'})

    def perform_create(self, serializer):
        aula_id = self.request.data.get('aula')
        if not aula_id:
            raise ValidationError({'aula': 'Campo "aula" é obrigatório.'})
        aula = get_object_or_404(
            Aula.objects.select_related('turma', 'turma__materia'),
            id=aula_id,
            turma__materia__professor=self.request.user,
        )

        professor = self.request.user
        instituicao = professor.instituicoes.filter(ativa=True).first() or professor.instituicao
        if instituicao:
            lat = instituicao.latitude
            lng = instituicao.longitude
            radius_value = instituicao.radius_meters
        else:
            # Compatibilidade temporária com professores criados antes do cadastro de instituições.
            lat = professor.latitude
            lng = professor.longitude
            radius_value = professor.radius_meters

        if lat is None or lng is None:
            raise ValidationError({
                'detail': 'A instituição precisa ter uma localização confirmada antes de iniciar a sessão.'
            })
        try:
            lat, lng = validate_coordinates(lat, lng)
            radius = validate_radius(radius_value)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc

        with chamada_atomic():
            Aula.objects.select_for_update().get(pk=aula.pk)
            existente = SessaoChamada.objects.select_for_update().filter(aula=aula, ativa=True).first()
            if existente:
                if not existente.is_token_valid():
                    existente.refresh_token()
                serializer.instance = existente
            else:
                serializer.save(
                    aula=aula,
                    professor_latitude=lat,
                    professor_longitude=lng,
                    professor_radius_meters=radius,
                )

    @action(detail=True, methods=['get'], url_path='token')
    def token(self, request, pk=None):
        sessao = self.get_object()
        with chamada_atomic():
            sessao = bloquear_sessao(sessao.pk)
            if not sessao.ativa:
                return Response({'detail': 'Sessão encerrada.'}, status=status.HTTP_400_BAD_REQUEST)
            if not sessao.is_token_valid():
                sessao.refresh_token()
            data = SessaoTokenSerializer(sessao).data
        # Renderiza fora da transação para não prolongar o bloqueio de escrita.
        data['qr_image'] = session_qr_image(request, sessao)
        data['servidor_agora'] = timezone.now()
        return Response(data, headers={'Cache-Control': 'no-store'})

    def perform_update(self, serializer):
        # PATCH/PUT de uma instância antiga também não pode reabrir a sessão.
        with chamada_atomic():
            serializer.instance = bloquear_sessao(serializer.instance.pk)
            serializer.save()

    def perform_destroy(self, instance):
        with chamada_atomic():
            bloquear_sessao(instance.pk).delete()

    @action(detail=True, methods=['get'], url_path='resultados')
    def resultados(self, request, pk=None):
        sessao = self.get_object()
        registros = sessao.presencas.select_related('aluno').order_by('aluno__username')
        registros = list(registros)
        total_alunos = TurmaAluno.objects.filter(turma=sessao.aula.turma).count()
        registrados_matriculados = TurmaAluno.objects.filter(turma=sessao.aula.turma, aluno_id__in=[registro.aluno_id for registro in registros]).count()
        return Response({'ativa': sessao.ativa, 'encerrada_em': sessao.encerrada_em, 'total_alunos': total_alunos, 'aguardando': total_alunos - registrados_matriculados, 'resultados': [{
            'aluno_id': registro.aluno_id,
            'aluno': registro.aluno.get_full_name() or registro.aluno.username,
            'status': 'presente' if registro.valida else 'falta',
            'horario': registro.registrada_em,
        } for registro in registros]})

    @action(detail=True, methods=['post'], url_path='encerrar')
    def encerrar(self, request, pk=None):
        sessao = self.get_object()
        with chamada_atomic():
            sessao = bloquear_sessao(sessao.pk)
            if not sessao.ativa:
                return Response({'detail': 'Sessão já está encerrada.'}, status=status.HTTP_400_BAD_REQUEST)
            sessao.ativa = False
            sessao.encerrada_em = timezone.now()
            sessao.save(update_fields=['ativa', 'encerrada_em'])
        return Response({'detail': 'Sessão encerrada com sucesso.'}, status=status.HTTP_200_OK)

class PresencaCreateView(viewsets.GenericViewSet):
    serializer_class = PresencaCreateSerializer
    permission_classes = [IsAluno]

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        presenca = serializer.save()
        return Response({
            'detail': 'Presença confirmada com sucesso.',
            'presenca': PresencaSerializer(presenca).data
        }, status=status.HTTP_201_CREATED if serializer.created else status.HTTP_200_OK)
