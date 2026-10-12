from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SessaoChamadaViewSet, PresencaCreateView

router = DefaultRouter()
router.register(r'sessoes', SessaoChamadaViewSet, basename='sessao')

urlpatterns = [
    path('', include(router.urls)),
    path('presenca/registrar/', PresencaCreateView.as_view({'post': 'create'}), name='presenca-registrar'),
]
