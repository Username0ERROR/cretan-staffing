from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0004_supportticket'),
    ]

    operations = [
        migrations.AddField(
            model_name='integrationcredential',
            name='endpoint_url',
            field=models.URLField(blank=True, help_text='HTTPS base URL for the connected system, such as a Horilla instance.', max_length=500),
        ),
    ]
