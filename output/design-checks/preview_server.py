"""Servidor descartável para revisão visual; nunca usa o banco do projeto."""
import sys
import tempfile
from datetime import date, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
from django.conf import settings

temporary = tempfile.TemporaryDirectory(prefix='aura-design-')
settings.DATABASES['default']['NAME'] = str(Path(temporary.name) / 'preview.sqlite3')
settings.MEDIA_ROOT = str(Path(temporary.name) / 'media')
settings.DEBUG = True
settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
settings.SESSION_COOKIE_SECURE = False
settings.CSRF_COOKIE_SECURE = False
settings.SECURE_SSL_REDIRECT = False
settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
settings.TEMPLATES[0]['APP_DIRS'] = False
settings.TEMPLATES[0]['OPTIONS']['loaders'] = [
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
]

import django
django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils import timezone
from courses.models import Instituicao, Materia, Turma, TurmaAluno, Aula
from attendance.models import SessaoChamada, Presenca

call_command('migrate', verbosity=0, interactive=False)
User = get_user_model()
teacher = User.objects.create_user(username='Docente Teste', password='Teste123!', role='professor', first_name='Rafael', last_name='Costa', email='docente@example.com')
student = User.objects.create_user(username='Aluno Teste', password='Teste123!', role='aluno', first_name='Camila', last_name='Santos', matricula='20260014', email='aluno@example.com')
campus = Instituicao.objects.create(nome='Campus Universitário', logradouro='Rua do Campus', numero='100', bairro='Centro', cidade='Campo Grande', estado='MS', latitude=-20.46, longitude=-54.61)
teacher.instituicoes.add(campus)
for i, name in enumerate(['Engenharia de Software', 'Banco de Dados', 'Redes de Computadores']):
    subject = Materia.objects.create(nome=name, codigo=f'TADS-0{i+1}', carga_horaria=60, professor=teacher)
    group = Turma.objects.create(nome=f'TADS · {i+3}º período', materia=subject, semestre='2º semestre', ano=2026)
    TurmaAluno.objects.create(turma=group, aluno=student)
    for j in range(4):
        lesson = Aula.objects.create(turma=group, titulo=['Projeto e arquitetura de sistemas', 'Modelagem e prática em laboratório', 'Revisão e atividade em equipe'][i], data=date.today()+timedelta(days=j-2), horario_inicio=time(19,0), horario_fim=time(20,40))
        if j < 3:
            session = SessaoChamada.objects.create(aula=lesson, ativa=False, encerrada_em=timezone.now(), professor_latitude=-20.46, professor_longitude=-54.61)
            if j != 2 or i == 0:
                Presenca.objects.create(sessao=session, aluno=student, latitude=-20.46, longitude=-54.61)
print('Preview isolada: http://127.0.0.1:8766', flush=True)
call_command('runserver', '127.0.0.1:8766', use_reloader=False, verbosity=0)
