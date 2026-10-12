"""Cenário fictício e repetível para apresentar as telas do AURA.

Identificação: e-mails @demo.aura.test, códigos DEMO-* e origem aura-demo-v1.
Não apaga registros nem redefine senhas de contas existentes.
"""
import os
import secrets
from collections import Counter
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from attendance.models import Presenca, SessaoChamada
from courses.models import Aula, Instituicao, Materia, Turma, TurmaAluno


SOURCE = 'aura-demo-v1'
DOMAIN = 'demo.aura.test'
INSTITUTIONS = (
    ('Centro Universitário Horizonte', 'Avenida do Conhecimento', '1200', 'Centro', 'Três Lagoas', 'MS', -20.787, -51.703),
    ('Instituto Superior Vale Verde', 'Rua das Acácias', '450', 'Jardim Universitário', 'Campo Grande', 'MS', -20.469, -54.620),
    ('Faculdade Nova Aurora', 'Avenida dos Ipês', '800', 'Vila Acadêmica', 'Andradina', 'SP', -20.896, -51.379),
)
TEACHERS = ('Mariana Costa', 'Rafael Almeida', 'Camila Rocha', 'André Nogueira')
STUDENTS = (
    'Lucas Martins', 'Beatriz Souza', 'João Pedro Lima', 'Ana Clara Ribeiro',
    'Gabriel Santos', 'Isabela Fernandes', 'Matheus Oliveira', 'Larissa Gomes',
    'Felipe Carvalho', 'Júlia Mendes', 'Gustavo Pereira', 'Mariana Alves',
    'Pedro Henrique Silva', 'Sofia Rodrigues', 'Bruno Teixeira', 'Luiza Barbosa',
    'Diego Moreira', 'Helena Cardoso', 'Vinícius Castro', 'Laura Azevedo',
    'Thiago Correia', 'Manuela Duarte', 'Rafael Monteiro', 'Clara Batista',
)
# código, nome, docente, carga horária, temas de oito encontros.
SUBJECTS = (
    ('BD202', 'Banco de Dados II', 0, 80, (
        'Modelagem relacional', 'Normalização de dados', 'Consultas com JOIN', 'Agregações e subconsultas',
        'Índices e desempenho', 'Transações e concorrência', 'Procedimentos e funções', 'Projeto prático de banco de dados',
    )),
    ('WEB204', 'Desenvolvimento Web', 0, 80, (
        'Estrutura semântica de páginas', 'Layouts responsivos', 'Formulários e acessibilidade', 'JavaScript e eventos',
        'Consumo de APIs', 'Autenticação e sessões', 'Testes de interface', 'Apresentação das aplicações',
    )),
    ('ES206', 'Engenharia de Software', 0, 60, (
        'Levantamento de requisitos', 'Casos de uso', 'Modelagem de domínio', 'Arquitetura de aplicações',
        'Versionamento em equipe', 'Testes automatizados', 'Revisão de código', 'Entrega incremental do projeto',
    )),
    ('RED201', 'Redes de Computadores', 1, 60, (
        'Fundamentos de redes', 'Modelo TCP/IP', 'Endereçamento IPv4', 'Sub-redes e roteamento',
        'DNS e serviços de rede', 'Redes sem fio', 'Segurança de redes', 'Diagnóstico em laboratório',
    )),
    ('UX203', 'Interação Humano-Computador', 2, 60, (
        'Pesquisa com usuários', 'Personas e jornadas', 'Arquitetura da informação', 'Prototipação de interfaces',
        'Acessibilidade digital', 'Testes de usabilidade', 'Avaliação heurística', 'Apresentação dos protótipos',
    )),
    ('ALG101', 'Algoritmos e Programação', 3, 80, (
        'Pensamento computacional', 'Variáveis e expressões', 'Estruturas condicionais', 'Laços de repetição',
        'Vetores e matrizes', 'Funções e modularização', 'Manipulação de arquivos', 'Desafio de programação',
    )),
)
# matéria, nome da turma, índices dos alunos, instituição, chamadas encerradas.
GROUPS = (
    (0, 'ADS · 4º período · Noturno', tuple(range(18)), 0, 8),
    (1, 'ADS · 4º período · Noturno', tuple(range(18)), 0, 8),
    (2, 'ADS · 4º período · Noturno', tuple(range(18)), 0, 8),
    (0, 'Sistemas de Informação · 4º período', tuple(range(12, 24)), 1, 8),
    (3, 'ADS · 4º período · Noturno', tuple(range(18)), 0, 8),
    (4, 'Sistemas de Informação · 4º período', tuple(range(12, 24)), 1, 8),
    (5, 'ADS · 2º período · Matutino', tuple(range(6, 24)), 2, 8),
    (2, 'ADS · Oficina de Projetos', tuple(range(8)), 0, 0),
)


class Command(BaseCommand):
    help = 'Cria dados fictícios para prints, preservando cadastros existentes e evitando duplicações.'

    def handle(self, *args, **options):
        self.created = Counter()
        self.new_accounts = []
        self.password = os.environ.get('AURA_DEMO_PASSWORD') or f'Aura-{secrets.token_urlsafe(12)}!'
        today = timezone.localdate()
        # Última sexta-feira anterior à data de execução; oito semanas de histórico.
        last_friday = today - timedelta(days=(today.weekday() - 4) % 7 or 7)
        self.first_day = last_friday - timedelta(weeks=7, days=4)
        self.enrolled_at = self.at(self.first_day - timedelta(days=7), time(9))

        with transaction.atomic():
            institutions = [self.institution(data) for data in INSTITUTIONS]
            teachers = [self.account(name, 'professor', institutions[(0, 0, 1, 2)[i]]) for i, name in enumerate(TEACHERS)]
            students = [self.account(name, 'aluno', institutions[0 if i < 12 else (1 if i < 18 else 2)], i)
                        for i, name in enumerate(STUDENTS)]
            subjects = []
            for code, name, teacher_index, hours, topics in SUBJECTS:
                subject, created = Materia.objects.get_or_create(
                    codigo=f'DEMO-{code}',
                    defaults={'nome': name, 'professor': teachers[teacher_index], 'carga_horaria': hours, 'frequencia_minima': 75},
                )
                if subject.professor_id != teachers[teacher_index].pk:
                    raise CommandError(f'O código DEMO-{code} já pertence a outro professor. Nenhum dado foi gravado.')
                self.created['matérias'] += created
                if created:
                    Materia.objects.filter(pk=subject.pk).update(created_at=self.enrolled_at - timedelta(days=1))
                subjects.append(subject)

            for index, (subject_index, name, student_indexes, institution_index, calls) in enumerate(GROUPS):
                institution = institutions[institution_index]
                subject = subjects[subject_index]
                subject.professor.instituicoes.add(institution)
                # A identidade não depende da data; repetir em outro dia não cria outra turma.
                group, created = Turma.objects.get_or_create(
                    materia=subject, nome=name,
                    defaults={'ano': today.year, 'semestre': '1º semestre' if today.month <= 6 else '2º semestre'},
                )
                self.created['turmas'] += created
                if created:
                    Turma.objects.filter(pk=group.pk).update(created_at=self.enrolled_at)
                for student_index in student_indexes:
                    enrollment, created = TurmaAluno.objects.get_or_create(turma=group, aluno=students[student_index])
                    self.created['vínculos'] += created
                    if created:
                        TurmaAluno.objects.filter(pk=enrollment.pk).update(data_entrada=self.enrolled_at)

                for week, topic in enumerate(SUBJECTS[subject_index][4][:calls]):
                    lesson, created = Aula.objects.get_or_create(
                        turma=group, titulo=f'{week + 1:02d} · {topic}',
                        defaults={'data': self.first_day + timedelta(weeks=week, days=index % 5),
                                  'horario_inicio': time(8 if index == 6 else 19),
                                  'horario_fim': time(10 if index == 6 else 21)},
                    )
                    self.created['aulas'] += created
                    if created:
                        Aula.objects.filter(pk=lesson.pk).update(criada_em=self.enrolled_at)
                    self.call(lesson, institution, student_indexes, students, index, week)

                # Agenda preenchida, sem deixar QR de uma chamada fictícia aberto.
                for offset, topic in enumerate(('Revisão e exercícios orientados', 'Oficina prática e acompanhamento')):
                    _, created = Aula.objects.get_or_create(
                        turma=group, titulo=topic,
                        defaults={'data': today + timedelta(days=1 + index % 5 + offset * 7),
                                  'horario_inicio': time(8 if index == 6 else 19),
                                  'horario_fim': time(10 if index == 6 else 21)},
                    )
                    self.created['aulas'] += created

        self.stdout.write(self.style.SUCCESS('Demonstração criada. Todos os nomes, endereços e registros são fictícios.'))
        self.stdout.write('Novos registros: ' + ', '.join(f'{total} {label}' for label, total in self.created.items()))
        if self.new_accounts:
            self.stdout.write(f'Senha das {len(self.new_accounts)} contas criadas nesta execução: {self.password}')
            for user in self.new_accounts:
                self.stdout.write(f'{user.get_role_display()}: {user.username} | {user.email}')
        else:
            self.stdout.write('Nenhuma conta nova. As senhas existentes foram mantidas.')
        self.stdout.write('Para os prints: entre como Mariana Costa (professora) ou Lucas Martins (aluno).')

    @staticmethod
    def at(day, hour):
        return timezone.make_aware(datetime.combine(day, hour))

    def institution(self, data):
        name, street, number, district, city, state, lat, lon = data
        institution, created = Instituicao.objects.get_or_create(nome=name, defaults={
            'logradouro': street, 'numero': number, 'bairro': district, 'cidade': city, 'estado': state,
            'latitude': lat, 'longitude': lon, 'radius_meters': 150, 'geocoding_source': SOURCE,
        })
        if not created and institution.geocoding_source != SOURCE:
            raise CommandError(f'A instituição {name} já existe fora da demonstração. Nenhum dado foi gravado.')
        self.created['instituições'] += created
        if created:
            Instituicao.objects.filter(pk=institution.pk).update(created_at=self.enrolled_at - timedelta(days=30))
        return institution

    def account(self, name, role, institution, index=None):
        User = get_user_model()
        email = f'{slugify(name)}@{DOMAIN}'
        matches = list(User.objects.filter(Q(username=name) | Q(email__iexact=email)))
        if matches:
            if len(matches) != 1 or matches[0].username != name or matches[0].email != email or matches[0].role != role:
                raise CommandError(f'O nome ou e-mail de {name} já está em uso fora da demonstração. Nenhum dado foi gravado.')
            return matches[0]
        first, last = name.split(' ', 1)
        user = User.objects.create_user(
            username=name, email=email, password=self.password, first_name=first, last_name=last,
            role=role, instituicao=institution, matricula=f'D2026{index + 1:04d}' if index is not None else None,
        )
        User.objects.filter(pk=user.pk).update(created_at=self.enrolled_at, date_joined=self.enrolled_at)
        if role == 'professor':
            user.instituicoes.add(institution)
        self.created['professores' if role == 'professor' else 'alunos'] += 1
        self.new_accounts.append(user)
        return user

    def call(self, lesson, institution, student_indexes, students, group_index, week):
        # Uma aula pode ganhar mais chamadas depois da demonstração. Preserve todas.
        if SessaoChamada.objects.filter(aula=lesson).exists():
            return
        start = self.at(lesson.data, lesson.horario_inicio) + timedelta(minutes=5)
        session = SessaoChamada.objects.create(
            aula=lesson, ativa=False, iniciada_em=start, encerrada_em=start + timedelta(minutes=20),
            token_expira_em=start + timedelta(seconds=30), professor_latitude=institution.latitude,
            professor_longitude=institution.longitude, professor_radius_meters=institution.radius_meters,
        )
        self.created['chamadas encerradas'] += 1
        targets = (8, 7, 6, 5, 4, 8, 7, 6, 8, 7, 3, 6)
        for student_index in student_indexes:
            # Lucas: 100%, 87,5%, 75% e 50% nas quatro matérias com histórico.
            target = (8, 7, 6, 5, 4, 8, 7, 6)[group_index] if student_index == 0 else targets[(student_index + group_index) % len(targets)]
            if (week + student_index * 3 + group_index) % 8 >= target:
                continue  # Falta é ausência de registro; não inventa falha de GPS.
            presence = Presenca.objects.create(
                sessao=session, aluno=students[student_index],
                latitude=institution.latitude + (student_index % 5 - 2) * 0.00004,
                longitude=institution.longitude + (student_index % 3 - 1) * 0.00004,
            )
            recorded = start + timedelta(minutes=1 + student_index % 14, seconds=student_index * 2)
            Presenca.objects.filter(pk=presence.pk).update(registrada_em=recorded, localizacao_capturada_em=recorded)
            self.created['presenças'] += 1
