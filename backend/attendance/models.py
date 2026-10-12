from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator
import secrets
from courses.models import Aula
from .geolocation import (
    MAX_RADIUS_METERS,
    MIN_RADIUS_METERS,
    is_within_radius,
)


class SessaoChamada(models.Model):
    id = models.AutoField(primary_key=True)
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE, related_name='sessoes')
    token_atual = models.CharField(max_length=100, unique=True, blank=True)
    token_expira_em = models.DateTimeField()
    ativa = models.BooleanField(default=True)
    iniciada_em = models.DateTimeField(default=timezone.now)
    encerrada_em = models.DateTimeField(null=True, blank=True)
    professor_latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    professor_longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    professor_radius_meters = models.PositiveIntegerField(
        default=100,
        validators=[
            MinValueValidator(MIN_RADIUS_METERS),
            MaxValueValidator(MAX_RADIUS_METERS),
        ],
    )

    class Meta:
        indexes = [
            models.Index(fields=['ativa'], name='idx_sessao_ativa'),
            models.Index(fields=['aula', 'ativa'], name='idx_sessao_aula_ativa'),
            models.Index(fields=['token_expira_em'], name='idx_sessao_token_exp'),
        ]

    def save(self, *args, **kwargs):
        if not self.token_atual:
            self.token_atual = secrets.token_urlsafe(16)
        if not self.token_expira_em:
            self.token_expira_em = timezone.now() + timezone.timedelta(seconds=30)
        super().save(*args, **kwargs)

    def is_token_valid(self):
        return self.ativa and timezone.now() < self.token_expira_em

    def refresh_token(self):
        self.token_atual = secrets.token_urlsafe(16)
        self.token_expira_em = timezone.now() + timezone.timedelta(seconds=30)
        self.save(update_fields=['token_atual', 'token_expira_em'])

    def __str__(self):
        return f"Sessao {self.id} - Aula {self.aula_id} - Token {'ativo' if self.is_token_valid() else 'expirado'}"


class Presenca(models.Model):
    id = models.AutoField(primary_key=True)
    sessao = models.ForeignKey(SessaoChamada, on_delete=models.CASCADE, related_name='presencas')
    aluno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='presencas')
    registrada_em = models.DateTimeField(auto_now_add=True)
    latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    localizacao_capturada_em = models.DateTimeField(auto_now_add=True)
    valida = models.BooleanField(default=False)

    class Meta:
        unique_together = ('sessao', 'aluno')
        indexes = [
            models.Index(fields=['valida'], name='idx_presenca_valida'),
            models.Index(fields=['aluno', 'registrada_em'], name='idx_pres_aluno_reg'),
            models.Index(fields=['sessao'], name='idx_presenca_sessao'),
            models.Index(fields=['sessao', 'aluno', 'valida'], name='idx_pres_ses_aln_val'),
        ]

    def save(self, *args, **kwargs):
        self.valida = is_within_radius(
            self.sessao.professor_latitude,
            self.sessao.professor_longitude,
            self.latitude,
            self.longitude,
            self.sessao.professor_radius_meters
        )
        self.localizacao_capturada_em = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Presença {self.aluno.username} na sessão {self.sessao_id} - {'Válida' if self.valida else 'Inválida'}"
