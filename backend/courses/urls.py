from rest_framework.routers import DefaultRouter
from .views import InstituicaoViewSet, MateriaViewSet, TurmaViewSet, AulaViewSet, TurmaAlunoViewSet

router = DefaultRouter()
router.register(r'instituicoes', InstituicaoViewSet, basename='instituicao')
router.register(r'materias', MateriaViewSet, basename='materia')
router.register(r'turmas', TurmaViewSet, basename='turma')
router.register(r'aulas', AulaViewSet, basename='aula')
router.register(r'turma-aluno', TurmaAlunoViewSet, basename='turma-aluno')

urlpatterns = router.urls