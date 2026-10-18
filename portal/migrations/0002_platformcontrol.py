from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformControl',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('maintenance_mode', models.BooleanField(default=False)),
                ('maintenance_message', models.CharField(
                    default='Cretan Staffing is temporarily undergoing scheduled maintenance. Please check back soon.',
                    max_length=240,
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Website availability',
                'verbose_name_plural': 'Website availability',
            },
        ),
    ]
