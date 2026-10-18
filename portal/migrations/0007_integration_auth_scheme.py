from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0006_accountsecurity'),
    ]

    operations = [
        migrations.AddField(
            model_name='integrationcredential',
            name='auth_scheme',
            field=models.CharField(choices=[('Bearer', 'Bearer token / OAuth'), ('Token', 'Token authentication')], default='Bearer', max_length=12),
        ),
    ]
