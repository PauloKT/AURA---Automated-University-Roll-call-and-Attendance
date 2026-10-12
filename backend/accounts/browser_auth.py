"""Autenticação do navegador por sessão Django, sem JWT acessível ao JavaScript."""
from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


@method_decorator(csrf_protect, name='dispatch')
class BrowserLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = AuthTokenSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user)
        return Response({'user': {'id': user.pk, 'username': user.username, 'role': user.role}},
                        headers={'Cache-Control': 'no-store'})


@method_decorator(csrf_protect, name='dispatch')
class BrowserLogoutView(APIView):
    # Idempotente, inclusive se a sessão expirou. O CSRF é exigido em todos os casos.
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        logout(request)
        return Response({'detail': 'Sessão encerrada.'}, headers={'Cache-Control': 'no-store'})
