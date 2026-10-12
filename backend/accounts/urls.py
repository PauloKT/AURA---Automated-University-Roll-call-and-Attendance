from django.urls import path
from .views import (
    RegisterView,
    CustomTokenObtainPairView,
    AlunoMinhaFrequenciaView,
    AlunoTurmasView,
    AlunoEntrarTurmaView,
)
from rest_framework_simplejwt.views import TokenRefreshView
from .browser_auth import BrowserLoginView, BrowserLogoutView

urlpatterns = [
    path('auth/login/', BrowserLoginView.as_view(), name='browser-login'),
    path('auth/logout/', BrowserLogoutView.as_view(), name='browser-logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('aluno/minha-frequencia/', AlunoMinhaFrequenciaView.as_view(), name='aluno-minha-frequencia'),
    path('aluno/turmas/', AlunoTurmasView.as_view(), name='aluno-turmas'),
    path('aluno/entrar-turma/', AlunoEntrarTurmaView.as_view(), name='aluno-entrar-turma'),
]
