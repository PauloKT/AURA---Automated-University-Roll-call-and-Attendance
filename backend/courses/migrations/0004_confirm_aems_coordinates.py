from django.db import migrations


def confirm_aems_coordinates(apps, schema_editor):
    instituicao = apps.get_model('courses', 'Instituicao')
    instituicao.objects.filter(nome='AEMS').update(
        latitude=-20.786820236467992,
        longitude=-51.668829782798554,
        geocoding_source='confirmacao_manual',
    )


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0003_seed_aems'),
    ]

    operations = [
        migrations.RunPython(confirm_aems_coordinates, migrations.RunPython.noop),
    ]