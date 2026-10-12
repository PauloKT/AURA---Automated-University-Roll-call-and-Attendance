from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.core.validators import MinValueValidator, MaxValueValidator
from uuid import uuid4

from .validators import SpacedUsernameValidator


def avatar_upload_to(instance, filename):
    return f'avatars/{instance.pk}/{uuid4().hex}.webp'


class CustomUser(AbstractUser):
    username_validator = SpacedUsernameValidator()
    username = models.CharField(
        'usuário', max_length=150, unique=True, validators=[username_validator],
        help_text='Até 150 caracteres. Letras, números, espaços e @ . + - _.',
        error_messages={'unique': 'Este nome de usuário já está em uso.'},
    )
    foto = models.FileField(upload_to=avatar_upload_to, blank=True)
    foto_posicao_x = models.FloatField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    foto_posicao_y = models.FloatField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    foto_zoom = models.FloatField(default=1, validators=[MinValueValidator(1), MaxValueValidator(3)])
    # Metadados legados preservados; não há mais autenticação pelo Google.
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True, editable=False)
    google_email = models.EmailField(blank=True, editable=False)
    ROLE_CHOICES = (
        ('professor', 'Professor'),
        ('aluno', 'Aluno'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    matricula = models.CharField(max_length=20, blank=True, null=True, help_text="Matrícula do aluno (opcional)")
    instituicao = models.ForeignKey(
        'courses.Instituicao',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios',
        limit_choices_to={'ativa': True},
        help_text='Instituição usada como referência de geolocalização.',
    )
    instituicoes = models.ManyToManyField(
        'courses.Instituicao',
        blank=True,
        related_name='professores',
        limit_choices_to={'ativa': True},
        help_text='Instituições onde o professor trabalha.',
    )
    # Mantidos para leitura dos cadastros anteriores às instituições.
    cep = models.CharField(max_length=9, blank=True, null=True, help_text="CEP da instituição (apenas para professores)")
    latitude = models.FloatField(blank=True, null=True, help_text="Latitude da instituição")
    longitude = models.FloatField(blank=True, null=True, help_text="Longitude da instituição")
    radius_meters = models.PositiveIntegerField(default=100, help_text="Raio de permissão em metros ao redor da instituição")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('email'), condition=~models.Q(email=''), name='accounts_email_ci_unique'),
        ]
        indexes = [
            models.Index(fields=['role'], name='idx_customuser_role'),
            models.Index(fields=['cep'], name='idx_customuser_cep'),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
