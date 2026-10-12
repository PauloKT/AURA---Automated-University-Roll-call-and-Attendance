from django.db import models
from django.conf import settings
import uuid
import secrets


def gerar_codigo_acesso():
    return ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))


class Instituicao(models.Model):
    """Local oficial usado como origem da cerca geográfica das sessões."""

    nome = models.CharField(max_length=150, unique=True)
    logradouro = models.CharField(max_length=200)
    numero = models.CharField(max_length=20)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    pais = models.CharField(max_length=80, default='Brasil')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    radius_meters = models.PositiveIntegerField(default=100)
    geocodificada_em = models.DateTimeField(null=True, blank=True)
    geocoding_source = models.CharField(max_length=100, blank=True, default='')
    ativa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['cidade', 'estado']),
            models.Index(fields=['ativa']),
        ]

    @property
    def endereco_completo(self):
        return (
            f'{self.logradouro}, {self.numero}, {self.bairro}, '
            f'{self.cidade}, {self.estado}, {self.pais}'
        )

    def __str__(self):
        return f'{self.nome} - {self.cidade}/{self.estado}'

class Materia(models.Model):
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, unique=True)
    carga_horaria = models.IntegerField(help_text="Carga horária total em horas")
    frequencia_minima = models.IntegerField(default=75, help_text="Percentual mínimo de frequência para aprovação")
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'professor'},
        related_name='materias'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.codigo})"

    class Meta:
        indexes = [
            models.Index(fields=['nome']),
            models.Index(fields=['professor']),
        ]


class Turma(models.Model):
    nome = models.CharField(max_length=100)
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='turmas')
    semestre = models.CharField(max_length=20)
    ano = models.IntegerField()
    link_acesso = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    codigo_acesso = models.CharField(max_length=8, default=gerar_codigo_acesso, unique=True, editable=False)
    ativa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.materia.nome} ({self.semestre}/{self.ano})"

    class Meta:
        indexes = [
            models.Index(fields=['ativa']),
            models.Index(fields=['ano', 'semestre']),
            models.Index(fields=['materia', 'ativa']),
        ]


class TurmaAluno(models.Model):
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name='alunos')
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'aluno'},
        related_name='turmas'
    )
    data_entrada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('turma', 'aluno')
        verbose_name = "Turma Aluno"
        verbose_name_plural = "Turmas Alunos"
        indexes = [
            models.Index(fields=['aluno']),
            models.Index(fields=['data_entrada']),
        ]

    def __str__(self):
        return f"{self.aluno.username} na {self.turma}"


class Aula(models.Model):
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name='aulas')
    titulo = models.CharField(max_length=200)
    data = models.DateField()
    horario_inicio = models.TimeField()
    horario_fim = models.TimeField()
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.titulo} - {self.turma} ({self.data})"

    class Meta:
        indexes = [
            models.Index(fields=['data']),
            models.Index(fields=['turma', 'data']),
            models.Index(fields=['criada_em']),
        ]
