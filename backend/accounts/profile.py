"""Perfil e fotos privadas: o endereço da imagem sempre aponta para o próprio usuário."""
import warnings
import math
from io import BytesIO
from pathlib import PurePosixPath

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse, Http404
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PHOTO_PIXELS = 20_000_000
CROP_DEFAULTS = {'foto_posicao_x': 50, 'foto_posicao_y': 50, 'foto_zoom': 1}


def profile_data(user):
    return {
        'id': user.pk, 'username': user.username,
        'nome': user.get_full_name() or user.username,
        'email': user.email, 'role': user.role, 'matricula': user.matricula,
        'instituicoes': list(user.instituicoes.values_list('nome', flat=True)),
        'foto_url': f'/api/interface/perfil/foto/?v={PurePosixPath(user.foto.name).stem}' if user.foto else None,
        **{field: getattr(user, field) for field in CROP_DEFAULTS},
    }


class ProfileSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=150, required=False)
    foto = serializers.FileField(required=False)
    foto_posicao_x = serializers.FloatField(min_value=0, max_value=100, required=False)
    foto_posicao_y = serializers.FloatField(min_value=0, max_value=100, required=False)
    foto_zoom = serializers.FloatField(min_value=1, max_value=3, required=False)

    def validate(self, attrs):
        for field in CROP_DEFAULTS:
            if field in attrs and not math.isfinite(attrs[field]):
                raise serializers.ValidationError({field: 'Informe um ajuste válido para a foto.'})
        return attrs

    def validate_nome(self, value):
        return ' '.join(value.split())

    def validate_foto(self, value):
        if value.size > MAX_PHOTO_BYTES:
            raise serializers.ValidationError('A foto deve ter até 5 MB.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(value) as original:
                    if original.format not in ('JPEG', 'PNG', 'WEBP'):
                        raise serializers.ValidationError('Escolha uma foto JPG, PNG ou WebP.')
                    if original.width * original.height > MAX_PHOTO_PIXELS:
                        raise serializers.ValidationError('A foto deve ter no máximo 20 megapixels.')
                    original.verify()
                value.seek(0)
                with Image.open(value) as original:
                    photo = ImageOps.exif_transpose(original)
                    photo.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    # Nova imagem sem EXIF (incluindo coordenadas GPS) nem outros metadados.
                    clean = Image.new('RGBA', photo.size)
                    clean.paste(photo.convert('RGBA'))
                    output = BytesIO()
                    clean.save(output, format='WEBP', quality=88)
            return ContentFile(output.getvalue(), name='avatar.webp')
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise serializers.ValidationError('Arquivo inválido. Escolha uma foto JPG, PNG ou WebP.')


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(profile_data(request.user), headers={'Cache-Control': 'no-store'})

    def patch(self, request):
        serializer = ProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = serializer.validated_data.get('foto')
        stored_name = None
        storage = User._meta.get_field('foto').storage
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=request.user.pk)
                fields = []
                crop = {field: serializer.validated_data[field] for field in CROP_DEFAULTS
                        if field in serializer.validated_data}
                if crop and photo is None and not user.foto:
                    raise serializers.ValidationError({'detail': 'Adicione uma foto antes de ajustar o enquadramento.'})
                if 'nome' in serializer.validated_data:
                    user.first_name, _, user.last_name = serializer.validated_data['nome'].partition(' ')
                    fields.extend(['first_name', 'last_name'])
                if photo is not None:
                    old_name = user.foto.name
                    user.foto.save(photo.name, photo, save=False)
                    stored_name = user.foto.name
                    fields.append('foto')
                    crop = {**CROP_DEFAULTS, **crop}
                    if old_name:
                        transaction.on_commit(lambda: storage.delete(old_name), robust=True)
                for field, value in crop.items():
                    setattr(user, field, value)
                    fields.append(field)
                if fields:
                    user.save(update_fields=fields)
        except Exception:
            if stored_name:
                storage.delete(stored_name)
            raise
        return Response(profile_data(user), headers={'Cache-Control': 'no-store'})


class ProfilePhotoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.foto:
            raise Http404
        try:
            photo = request.user.foto.open('rb')
        except FileNotFoundError:
            raise Http404
        response = FileResponse(photo, content_type='image/webp')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    def delete(self, request):
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            old_name, storage = user.foto.name, user.foto.storage
            user.foto = ''
            for field, value in CROP_DEFAULTS.items():
                setattr(user, field, value)
            user.save(update_fields=['foto', *CROP_DEFAULTS])
            if old_name:
                transaction.on_commit(lambda: storage.delete(old_name), robust=True)
        return Response(profile_data(user), headers={'Cache-Control': 'no-store'})
