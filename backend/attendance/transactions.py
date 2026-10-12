"""Transações curtas compartilhadas pelas operações de uma chamada no SQLite."""
from contextlib import contextmanager
import sqlite3

from django.db import OperationalError, transaction
from rest_framework.exceptions import APIException, ValidationError

from .models import SessaoChamada


class ChamadaOcupada(APIException):
    status_code = 503
    default_detail = 'A chamada está ocupada no momento. Aguarde alguns segundos e tente novamente.'
    default_code = 'chamada_ocupada'


@contextmanager
def chamada_atomic():
    """Não refaz envios automaticamente; devolve erro temporário se o SQLite saturar."""
    try:
        with transaction.atomic():
            yield
    except OperationalError as exc:
        code = getattr(exc.__cause__, 'sqlite_errorcode', None)
        if code is not None and (code & 0xff) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            raise ChamadaOcupada() from exc
        raise


def bloquear_sessao(sessao_id):
    """Recarrega a sessão dentro de chamada_atomic, que reserva a escrita."""
    sessao = SessaoChamada.objects.filter(pk=sessao_id).first()
    if sessao is None:
        raise ValidationError({'sessao_id': 'Sessão não encontrada.'})
    return sessao
