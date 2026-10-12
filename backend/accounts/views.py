from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from courses.models import Turma, TurmaAluno
from attendance.frequency import consultar_frequencias
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
        frequencias = consultar_frequencias([turma.pk], aluno_id=request.user.pk)
        if not frequencias.vinculos:
            return Response({'detail': 'Você não está matriculado nesta turma.'}, status=status.HTTP_403_FORBIDDEN)
        frequencia = frequencias.vinculos[0]
        return Response({'percentual': frequencia.percentual, 'situacao': frequencia.situacao})


class AlunoTurmasView(AlunoView):
    def get(self, request):
        turma_ids = Turma.objects.filter(alunos__aluno=request.user).values_list('pk', flat=True)
        frequencias = consultar_frequencias(turma_ids, aluno_id=request.user.pk)
        resultado = []
        for frequencia in frequencias.vinculos:
            turma = frequencia.vinculo.turma
            resultado.append({
                'turma_id': turma.id, 'nome': turma.nome,
                'materia': {'id': turma.materia.id, 'nome': turma.materia.nome, 'codigo': turma.materia.codigo},
                'semestre': turma.semestre, 'ano': turma.ano, 'ativa': turma.ativa,
                'percentual': frequencia.percentual, 'situacao': frequencia.situacao,
                'professor': turma.materia.professor.get_full_name() or turma.materia.professor.username,
                'presencas': frequencia.presencas,
                'faltas': frequencia.faltas,
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
