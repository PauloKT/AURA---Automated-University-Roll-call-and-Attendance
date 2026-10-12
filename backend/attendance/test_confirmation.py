"""Regressões do fluxo QR/GPS; executa com o test runner nativo do Django."""
from base64 import b64decode
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

import qrcode
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from courses.models import Aula, Materia, Turma, TurmaAluno
from .models import Presenca, SessaoChamada
from .serializers import PresencaCreateSerializer


@override_settings(ALLOWED_HOSTS=['testserver', 'aura.test'])
class ConfirmationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.professor = user.objects.create_user(username='prof', role='professor')
        cls.aluno = user.objects.create_user(username='aluno', role='aluno')
        cls.outro = user.objects.create_user(username='outro', role='aluno')
        cls.outro_professor = user.objects.create_user(username='outro-prof', role='professor')
        materia = Materia.objects.create(nome='Teste', codigo='TST', carga_horaria=40, professor=cls.professor)
        cls.turma = Turma.objects.create(nome='Turma', materia=materia, semestre='2', ano=2026)
        cls.aula = Aula.objects.create(
            turma=cls.turma, titulo='Aula', data='2026-10-01',
            horario_inicio='19:00', horario_fim='20:00',
        )
        TurmaAluno.objects.create(turma=cls.turma, aluno=cls.aluno)

    def setUp(self):
        self.sessao = SessaoChamada.objects.create(
            aula=self.aula, professor_latitude=-20.78, professor_longitude=-51.66,
            professor_radius_meters=100,
        )
        self.client.force_authenticate(self.aluno)

    def payload(self, **changes):
        return {
            'sessao_id': self.sessao.pk, 'token': self.sessao.token_atual,
            'latitude': -20.78, 'longitude': -51.66, **changes,
        }

    def register(self, **changes):
        return self.client.post('/api/presenca/registrar/', self.payload(**changes), format='json')

    def prepare(self):
        return self.client.post(
            f'/api/sessoes/{self.sessao.pk}/preparar/',
            {'token': self.sessao.token_atual}, format='json',
        )

    def expire(self):
        self.sessao.token_expira_em = timezone.now() - timezone.timedelta(seconds=1)
        self.sessao.save(update_fields=['token_expira_em'])

    def test_outside_radius_does_not_save_and_retry_confirms(self):
        failed = self.register(latitude=-21)
        self.assertEqual(failed.status_code, 400)
        self.assertIn('fora do raio', str(failed.data['detail']))
        self.assertFalse(Presenca.objects.exists())
        self.assertEqual(len(self.client.get('/api/sessoes/ativas/').data['chamadas']), 1)
        confirmed = self.register()
        self.assertEqual(confirmed.status_code, 201)
        self.assertIs(confirmed.data['presenca']['valida'], True)
        self.assertEqual(Presenca.objects.count(), 1)
        self.assertEqual(self.client.get('/api/sessoes/ativas/').data['chamadas'], [])

    def test_wrong_token_does_not_save_and_retry_confirms(self):
        self.assertEqual(self.register(token='wrong').status_code, 400)
        self.assertFalse(Presenca.objects.exists())
        self.assertIs(self.register().data['presenca']['valida'], True)

    def test_expired_token_does_not_save_and_new_token_confirms(self):
        self.expire()
        self.assertEqual(self.register().status_code, 400)
        self.assertEqual(self.prepare().status_code, 400)
        self.assertFalse(Presenca.objects.exists())
        self.sessao.refresh_token()
        self.assertIs(self.register().data['presenca']['valida'], True)

    def test_legacy_invalid_record_can_be_corrected_without_duplicate(self):
        legacy = Presenca.objects.create(sessao=self.sessao, aluno=self.aluno, latitude=-21, longitude=-51.66)
        self.assertFalse(legacy.valida)
        self.assertEqual(len(self.client.get('/api/sessoes/ativas/').data['chamadas']), 1)
        result = self.register()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['presenca']['id'], legacy.pk)
        legacy.refresh_from_db()
        self.assertTrue(legacy.valida)
        self.assertEqual(legacy.latitude, -20.78)
        self.assertEqual(Presenca.objects.count(), 1)

    def test_duplicate_preserves_confirmed_location_and_timestamp(self):
        first = self.register().data['presenca']
        second = self.register(latitude=-20.78001)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['presenca'], first)
        self.assertEqual(self.register(latitude=-21).status_code, 400)
        self.assertTrue(Presenca.objects.get().valida)
        self.assertEqual(Presenca.objects.count(), 1)

    def test_enrollment_required_for_preparation_and_registration(self):
        self.client.force_authenticate(self.outro)
        self.assertEqual(self.prepare().status_code, 404)
        self.assertEqual(self.register().status_code, 400)
        self.assertFalse(Presenca.objects.exists())
        self.assertEqual(self.client.get('/api/sessoes/ativas/').data['chamadas'], [])

    def test_student_cannot_read_token_or_qr_and_listing_has_no_secrets(self):
        listing = self.client.get('/api/sessoes/ativas/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(set(listing.data['chamadas'][0]), {
            'id', 'turma_id', 'turma', 'materia', 'aula', 'iniciada_em',
        })
        self.assertNotIn(self.sessao.token_atual, listing.content.decode())
        for path in ('/api/sessoes/', f'/api/sessoes/{self.sessao.pk}/', f'/api/sessoes/{self.sessao.pk}/token/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get('/api/aluno/sessoes-ativas/').status_code, 404)

    def test_only_owner_can_read_qr(self):
        self.client.force_authenticate(self.outro_professor)
        self.assertEqual(self.client.get(f'/api/sessoes/{self.sessao.pk}/token/').status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/api/sessoes/{self.sessao.pk}/token/').status_code, 401)

    def test_qr_is_local_svg_and_contains_current_session_url(self):
        self.client.force_authenticate(self.professor)
        with patch('attendance.qr.qrcode.make', wraps=qrcode.make) as make:
            result = self.client.get(
                f'/api/sessoes/{self.sessao.pk}/token/', {'origin': 'https://aura.test'}, HTTP_HOST='aura.test',
            )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result['Cache-Control'], 'no-store')
        prefix, encoded = result.data['qr_image'].split(',', 1)
        self.assertEqual(prefix, 'data:image/svg+xml;base64')
        svg = ElementTree.fromstring(b64decode(encoded))
        self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
        self.assertIsNotNone(svg.find('{http://www.w3.org/2000/svg}path'))
        url = urlsplit(make.call_args.args[0])
        self.assertEqual((url.scheme, url.netloc, url.path), ('https', 'aura.test', '/confirmar-presenca.html'))
        self.assertEqual(parse_qs(url.query), {'sessaoId': [str(self.sessao.pk)], 'token': [self.sessao.token_atual]})

    def test_qr_rejects_external_origin(self):
        self.client.force_authenticate(self.professor)
        result = self.client.get(f'/api/sessoes/{self.sessao.pk}/token/', {'origin': 'https://evil.test'})
        self.assertEqual(result.status_code, 400)

    def test_qr_renews_expired_token_once_and_stops_when_closed(self):
        self.client.force_authenticate(self.professor)
        old = self.sessao.token_atual
        self.expire()
        path = f'/api/sessoes/{self.sessao.pk}/token/'
        first = self.client.get(path)
        second = self.client.get(path)
        self.assertNotEqual(first.data['token_atual'], old)
        self.assertEqual(first.data['token_atual'], second.data['token_atual'])
        self.assertEqual(first.data['qr_image'], second.data['qr_image'])
        self.client.post(f'/api/sessoes/{self.sessao.pk}/encerrar/')
        self.assertEqual(self.client.get(path).status_code, 400)

    def test_receipt_allows_gps_retry_after_qr_rotation(self):
        prepared = self.prepare()
        self.assertEqual(prepared['Cache-Control'], 'no-store')
        receipt = prepared.data['comprovante']
        self.sessao.refresh_token()
        self.assertEqual(self.register(token='old-token', comprovante=receipt, latitude=-21).status_code, 400)
        self.assertFalse(Presenca.objects.exists())
        self.assertIs(self.register(token='old-token', comprovante=receipt).data['presenca']['valida'], True)

    def test_receipt_is_bound_to_student_and_session(self):
        receipt = self.prepare().data['comprovante']
        TurmaAluno.objects.create(turma=self.turma, aluno=self.outro)
        self.client.force_authenticate(self.outro)
        self.assertEqual(self.register(comprovante=receipt).status_code, 400)
        self.client.force_authenticate(self.aluno)
        other_session = SessaoChamada.objects.create(
            aula=self.aula, professor_latitude=-20.78, professor_longitude=-51.66,
        )
        self.assertEqual(self.register(sessao_id=other_session.pk, comprovante=receipt).status_code, 400)
        self.assertFalse(Presenca.objects.exists())

    def test_expired_or_tampered_receipt_does_not_save(self):
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() - 121):
            receipt = signing.dumps({'sessao': self.sessao.pk, 'aluno': self.aluno.pk}, salt='attendance.scan')
        for value in (receipt, receipt + 'tampered'):
            with self.subTest(receipt=value):
                self.assertEqual(self.register(comprovante=value).status_code, 400)
        self.assertFalse(Presenca.objects.exists())

    def test_closed_session_blocks_retry(self):
        receipt = self.prepare().data['comprovante']
        self.sessao.ativa = False
        self.sessao.save(update_fields=['ativa'])
        self.assertEqual(self.register(comprovante=receipt).status_code, 400)
        self.assertFalse(Presenca.objects.exists())

    def test_invalid_coordinates_do_not_save(self):
        for coordinate in (91, 'NaN', 'Infinity'):
            with self.subTest(coordinate=coordinate):
                self.assertEqual(self.register(latitude=coordinate).status_code, 400)
        self.assertFalse(Presenca.objects.exists())

    def test_session_changes_after_validation_are_rechecked_before_save(self):
        for change in ('token', 'closed', 'radius', 'enrollment'):
            with self.subTest(change=change):
                serializer = PresencaCreateSerializer(
                    data=self.payload(), context={'request': SimpleNamespace(user=self.aluno)},
                )
                serializer.is_valid(raise_exception=True)
                if change == 'token':
                    self.sessao.refresh_token()
                elif change == 'closed':
                    SessaoChamada.objects.filter(pk=self.sessao.pk).update(ativa=False)
                elif change == 'radius':
                    SessaoChamada.objects.filter(pk=self.sessao.pk).update(professor_latitude=-21)
                else:
                    TurmaAluno.objects.filter(turma=self.turma, aluno=self.aluno).delete()
                with self.assertRaises(ValidationError):
                    serializer.save()
                self.assertFalse(Presenca.objects.exists())
                SessaoChamada.objects.filter(pk=self.sessao.pk).update(ativa=True, professor_latitude=-20.78)

    def test_professor_cannot_register_student_attendance(self):
        self.client.force_authenticate(self.professor)
        self.assertEqual(self.register().status_code, 403)
        self.assertFalse(Presenca.objects.exists())
