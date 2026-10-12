from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0004_alter_presenca_latitude_alter_presenca_longitude_and_more'),
    ]

    operations = [
        migrations.RemoveField(model_name='presenca', name='webauthn_verified'),
        migrations.DeleteModel(name='WebAuthnChallenge'),
        migrations.DeleteModel(name='WebAuthnCredential'),
    ]
