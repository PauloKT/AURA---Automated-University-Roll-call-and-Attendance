from django.db import migrations, models


def copy_primary_institution(apps, schema_editor):
    user = apps.get_model('accounts', 'CustomUser')
    for professor in user.objects.exclude(instituicao__isnull=True):
        professor.instituicoes.add(professor.instituicao_id)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_customuser_instituicao'),
        ('courses', '0004_confirm_aems_coordinates'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='instituicoes',
            field=models.ManyToManyField(
                blank=True,
                help_text='Instituições onde o professor trabalha.',
                limit_choices_to={'ativa': True},
                related_name='professores',
                to='courses.instituicao',
            ),
        ),
        migrations.RunPython(copy_primary_institution, migrations.RunPython.noop),
    ]