from django.db import migrations, models
import courses.models


def preencher_codigos(apps, schema_editor):
    Turma = apps.get_model('courses', 'Turma')
    database = schema_editor.connection.alias
    usados = set()
    for turma in Turma.objects.using(database).all().iterator():
        codigo = courses.models.gerar_codigo_acesso()
        while codigo in usados:
            codigo = courses.models.gerar_codigo_acesso()
        usados.add(codigo)
        turma.codigo_acesso = codigo
        turma.save(using=database, update_fields=['codigo_acesso'])


class Migration(migrations.Migration):
    dependencies = [('courses', '0004_confirm_aems_coordinates')]
    operations = [
        migrations.AddField(
            model_name='turma', name='codigo_acesso',
            field=models.CharField(max_length=8, null=True, editable=False),
        ),
        migrations.RunPython(preencher_codigos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='turma', name='codigo_acesso',
            field=models.CharField(max_length=8, unique=True, editable=False, default=courses.models.gerar_codigo_acesso),
        ),
    ]
