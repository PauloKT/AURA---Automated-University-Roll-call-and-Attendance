"""Atualiza o SQLite local após criar uma cópia de segurança."""
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command


class Command(BaseCommand):
    help = 'Faz backup do SQLite e aplica migrations locais.'

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if database['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Este comando é exclusivo para SQLite local.')
        source = Path(database['NAME']).resolve()
        if source.parent != settings.BASE_DIR.resolve():
            raise CommandError('O banco deve estar no diretório backend do projeto.')
        if source.exists():
            directory = source.parent / 'backups'
            directory.mkdir(exist_ok=True)
            backup = directory / f'aura-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3'
            with sqlite3.connect(source) as original, sqlite3.connect(backup) as copied:
                original.backup(copied)
            self.stdout.write(f'Backup criado: {backup}')
        call_command('migrate', interactive=False)
        call_command('check')
