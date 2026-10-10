from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from .ui_api import WorkspaceView
from accounts.profile import ProfileView, ProfilePhotoView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path('', TemplateView.as_view(template_name='login.html'), name='home'),
    path('login.html', TemplateView.as_view(template_name='login.html'), name='login-page'),
    path('register.html', TemplateView.as_view(template_name='register.html'), name='register-page'),
    path('professor.html', TemplateView.as_view(template_name='professor.html', extra_context={'area': 'professor'}), name='professor-page'),
    path('aluno.html', TemplateView.as_view(template_name='aluno.html', extra_context={'area': 'aluno'}), name='aluno-page'),
    path('confirmar-presenca.html', TemplateView.as_view(template_name='confirmar-presenca.html', extra_context={'area': 'aluno'}), name='presence-page'),
    path('api/interface/painel/', WorkspaceView.as_view(), name='workspace-data'),
    path('api/interface/perfil/', ProfileView.as_view(), name='profile-data'),
    path('api/interface/perfil/foto/', ProfilePhotoView.as_view(), name='profile-photo'),
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),
    path('api/', include('courses.urls')),
    path('api/', include('attendance.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
