from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from courses.models import Turma, TurmaAluno
from attendance.models import SessaoChamada
from .serializers import UserRegistrationSerializer, CustomTokenObtainPairSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError:
            raise serializers.ValidationError({'detail': 'Usuário ou e-mail já cadastrado. Entre na sua conta.'})
        return Response({
            'user': {'id': user.id, 'username': user.username, 'email': user.email, 'role': user.role},
            'message': 'Usuário criado com sucesso.',
        }, status=status.HTTP_201_CREATED, headers=self.get_success_headers(serializer.data))


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


def frequency_result(total, attended, minimum):
    if not total:
        return 0.0, 'sem_dados'
    percentage = attended / total * 100
    return round(percentage, 2), 'aprovado' if percentage >= minimum else 'reprovado'


def _calcular_frequencia(aluno, turma):
    counts = SessaoChamada.objects.filter(aula__turma=turma, ativa=False).aggregate(
        total=Count('id', distinct=True),
        attended=Count('id', filter=Q(presencas__aluno=aluno, presencas__valida=True), distinct=True),
    )
    return frequency_result(counts['total'], counts['attended'], turma.materia.frequencia_minima)


class AlunoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.role != 'aluno':
            self.permission_denied(request, message='Apenas alunos podem acessar esta informação.')


class AlunoMinhaFrequenciaView(AlunoView):
    def get(self, request):
        turma_id = serializers.IntegerField(min_value=1).run_validation(request.query_params.get('turma'))
        turma = get_object_or_404(Turma.objects.select_related('materia'), pk=turma_id)
        if not TurmaAluno.objects.filter(turma=turma, aluno=request.user).exists():
            return Response({'detail': 'Você não está matriculado nesta turma.'}, status=status.HTTP_403_FORBIDDEN)
        percentual, situacao = _calcular_frequencia(request.user, turma)
        return Response({'percentual': percentual, 'situacao': situacao})


class AlunoTurmasView(AlunoView):
    def get(self, request):
        turmas = Turma.objects.filter(alunos__aluno=request.user).select_related('materia', 'materia__professor').annotate(
            total_sessoes=Count('aulas__sessoes', filter=Q(aulas__sessoes__ativa=False), distinct=True),
            presencas_validas=Count(
                'aulas__sessoes__presencas',
                filter=Q(aulas__sessoes__ativa=False,
                         aulas__sessoes__presencas__aluno=request.user,
                         aulas__sessoes__presencas__valida=True),
                distinct=True,
            ),
        )
        resultado = []
        for turma in turmas:
            percentual, situacao = frequency_result(
                turma.total_sessoes, turma.presencas_validas, turma.materia.frequencia_minima,
            )
            resultado.append({
                'turma_id': turma.id, 'nome': turma.nome,
                'materia': {'id': turma.materia.id, 'nome': turma.materia.nome, 'codigo': turma.materia.codigo},
                'semestre': turma.semestre, 'ano': turma.ano, 'ativa': turma.ativa,
                'percentual': percentual, 'situacao': situacao,
                'professor': turma.materia.professor.get_full_name() or turma.materia.professor.username,
                'presencas': turma.presencas_validas,
                'faltas': turma.total_sessoes - turma.presencas_validas,
            })
        return Response({'turmas': resultado})


class AlunoEntrarTurmaView(AlunoView):
    def post(self, request):
        if 'codigo_acesso' in request.data:
            codigo = serializers.CharField(max_length=8).run_validation(request.data['codigo_acesso']).upper()
            turma = Turma.objects.filter(codigo_acesso=codigo, ativa=True).first()
            if turma is None:
                raise serializers.ValidationError({'detail': 'Código inválido ou turma inativa. Confira com o professor.'})
        else:
            link = serializers.UUIDField().run_validation(request.data.get('link_acesso'))
            turma = get_object_or_404(Turma, link_acesso=link, ativa=True)
        _, created = TurmaAluno.objects.get_or_create(turma=turma, aluno=request.user)
        return Response({
            'detail': 'Matriculado com sucesso.' if created else 'Você já está matriculado nesta turma.',
            'turma_id': turma.id,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
