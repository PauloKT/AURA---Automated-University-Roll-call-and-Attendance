from django.db import migrations


AEMS_ADDRESS = {
    'nome': 'AEMS',
    'logradouro': 'Av. Júlio Ferreira Xavier',
    'numero': '2750',
    'bairro': 'Distrito Industrial',
    'cidade': 'Três Lagoas',
    'estado': 'MS',
    'pais': 'Brasil',
    'radius_meters': 100,
    'latitude': -20.786820236467992,
    'longitude': -51.668829782798554,
    'ativa': True,
}


def create_aems(apps, schema_editor):
    """Cadastra a instituição inicial usada nos testes do TCC."""
    instituicao = apps.get_model('courses', 'Instituicao')
    instituicao.objects.get_or_create(nome='AEMS', defaults=AEMS_ADDRESS)


def remove_aems(apps, schema_editor):
    instituicao = apps.get_model('courses', 'Instituicao')
    instituicao.objects.filter(nome='AEMS').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0002_instituicao'),
    ]

    operations = [
        migrations.RunPython(create_aems, remove_aems),
    ]
