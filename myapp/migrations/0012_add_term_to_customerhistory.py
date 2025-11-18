# Generated manually to add term field to CustomerHistory

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0011_auto_20251102_1350'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerhistory',
            name='term',
            field=models.IntegerField(default=0),
        ),
    ]
