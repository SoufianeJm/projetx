# Generated by Django 5.0.2 on 2025-05-24 19:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0007_swap_mission_field_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mission',
            name='belgian_name',
            field=models.CharField(max_length=255, verbose_name='Libellé de Projet'),
        ),
        migrations.AlterField(
            model_name='mission',
            name='libelle_de_projet',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Belgian Name'),
        ),
    ]
