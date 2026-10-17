# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0021_alter_authenticationpin_create_time_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='notifications',
            name='is_read',
            field=models.BooleanField(default=False),
        ),
    ]

