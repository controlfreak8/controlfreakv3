# Generated by Django 4.2 on 2023-11-17 20:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('controlfreakapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tertiarycontrolfile',
            name='file',
            field=models.FileField(upload_to=''),
        ),
    ]
