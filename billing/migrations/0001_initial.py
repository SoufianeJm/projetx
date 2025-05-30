# Generated by Django 5.2.1 on 2025-05-24 14:56

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Mission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('otp_l2', models.CharField(max_length=100, unique=True, verbose_name='OTP L2 (Swift Code)')),
                ('belgian_name', models.CharField(max_length=255, verbose_name='Belgian Name')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Comment')),
            ],
        ),
        migrations.CreateModel(
            name='Resource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255, verbose_name='Full Name')),
                ('picture', models.ImageField(blank=True, null=True, upload_to='resource_pictures/', verbose_name='Picture')),
                ('matricule', models.CharField(max_length=50, unique=True, verbose_name='Matricule')),
                ('rate_ibm', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Rate IBM')),
                ('rate_des', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Rate DES')),
                ('rank', models.CharField(max_length=100, verbose_name='Rank')),
            ],
        ),
    ]
