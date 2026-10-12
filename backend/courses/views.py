from math import isfinite

from django.utils import timezone
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Instituicao, Materia, Turma, Aula, TurmaAluno
from .geocoding import geocode_address
from .serializers import (
    MateriaSerializer,
    TurmaSerializer,
    AulaSerializer,
    TurmaAlunoSerializer,
    InstituicaoSerializer,
    InstituicaoCatalogoSerializer,
)


class InstituicaoViewSet(viewsets.ReadOnlyModelViewSet):
    """Lista instituições ativas e permite geocodificação administrativa."""

    queryset = Instituicao.objects.filter(ativa=True)
    serializer_class = InstituicaoSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny],
            serializer_class=InstituicaoCatalogoSerializer)
    def catalogo(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAdminUser],
        url_path='geocodificar',
    )
    def geocodificar(self, request, pk=None):
        instituicao = self.get_object()
        return Response({
            'instituicao': instituicao.nome,
            'endereco': instituicao.endereco_completo,
            'candidatos': geocode_address(instituicao.endereco_completo),
        })

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAdminUser],
        url_path='confirmar-localizacao',
    )
    def confirmar_localizacao(self, request, pk=None):
        """Confirma manualmente a coordenada oficial após conferência."""
        instituicao = self.get_object()
        try:
            latitude = float(request.data['latitude'])
            longitude = float(request.data['longitude'])
        except (KeyError, TypeError, ValueError):
            return Response(
                {'detail': 'Latitude e longitude são obrigatórias e numéricas.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            not isfinite(latitude)
            or not isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            return Response(
                {'detail': 'Latitude deve estar entre -90 e 90; longitude entre -180 e 180.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instituicao.latitude = latitude
        instituicao.longitude = longitude
        instituicao.geocodificada_em = timezone.now()
        instituicao.geocoding_source = serializers.CharField(max_length=100).run_validation(
            request.data.get('source', 'confirmacao_manual'),
        )
        instituicao.save(update_fields=[
            'latitude', 'longitude', 'geocodificada_em', 'geocoding_source',
        ])
        return Response(InstituicaoSerializer(instituicao).data)

class IsProfessorOrReadOnly(permissions.BasePermission):
    """Permite alterações apenas a professores."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.role == 'professor'

class MateriaViewSet(viewsets.ModelViewSet):
    queryset = Materia.objects.all()
    serializer_class = MateriaSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfessorOrReadOnly]

    def get_queryset(self):
        queryset = Materia.objects.select_related('professor')
        if self.request.user.role == 'professor':
            return queryset.filter(professor=self.request.user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(professor=self.request.user)

class TurmaViewSet(viewsets.ModelViewSet):
    queryset = Turma.objects.all()
    serializer_class = TurmaSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfessorOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'professor':
            queryset = Turma.objects.filter(materia__professor=user)
        elif user.role == 'aluno':
            queryset = Turma.objects.filter(alunos__aluno=user)
        else:
            return Turma.objects.none()

        materia_id = self.request.query_params.get('materia')
        if materia_id:
            materia_id = serializers.IntegerField(min_value=1).run_validation(materia_id)
            queryset = queryset.filter(materia_id=materia_id)

        return queryset.select_related('materia').distinct()

class AulaViewSet(viewsets.ModelViewSet):
    queryset = Aula.objects.all()
    serializer_class = AulaSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfessorOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'professor':
            queryset = Aula.objects.filter(turma__materia__professor=user)
        elif user.role == 'aluno':
            queryset = Aula.objects.filter(turma__alunos__aluno=user)
        else:
            return Aula.objects.none()

        turma_id = self.request.query_params.get('turma')
        if turma_id:
            turma_id = serializers.IntegerField(min_value=1).run_validation(turma_id)
            queryset = queryset.filter(turma_id=turma_id)

        return queryset.select_related('turma').distinct()

class TurmaAlunoViewSet(viewsets.ModelViewSet):
    queryset = TurmaAluno.objects.all()
    serializer_class = TurmaAlunoSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfessorOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'professor':
            return TurmaAluno.objects.filter(turma__materia__professor=user).select_related('turma', 'aluno')
        elif user.role == 'aluno':
            return TurmaAluno.objects.filter(aluno=user).select_related('turma', 'aluno')
        return TurmaAluno.objects.none()
