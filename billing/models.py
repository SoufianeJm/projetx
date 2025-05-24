from django.db import models
from django.urls import reverse

# Create your models here.

class Resource(models.Model):
    full_name = models.CharField(max_length=255, verbose_name="Full Name")
    picture = models.ImageField(upload_to='resources/', null=True, blank=True, verbose_name="Profile Picture")
    matricule = models.CharField(max_length=50, unique=True, verbose_name="Matricule")
    rate_ibm = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Rate IBM")
    rate_des = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Rate DES")
    rank = models.CharField(max_length=50, verbose_name="Rank")

    def __str__(self):
        return self.full_name

    def get_absolute_url(self):
        return reverse('resource_detail', kwargs={'pk': self.pk})

class Mission(models.Model):
    # Define choices for code_type
    CODE_FRANCE = 'FR'
    CODE_DES = 'DES'
    CODE_TYPE_CHOICES = [
        (CODE_FRANCE, 'Code France'),
        (CODE_DES, 'Code DES'),
    ]

    otp_l2 = models.CharField(max_length=100, unique=True, verbose_name="OTP L2 (Swift Code)")
    belgian_name = models.CharField(max_length=255, verbose_name="Belgian Name")
    libelle_de_projet = models.CharField(max_length=255, verbose_name="Libellé de Projet", blank=True, null=True)
    code_type = models.CharField(
        max_length=3,
        choices=CODE_TYPE_CHOICES,
        default=CODE_FRANCE,
        verbose_name="Type de Code",
        blank=False,
        null=False
    )

    def __str__(self):
        return f"{self.otp_l2} - {self.libelle_de_projet or self.belgian_name} ({self.get_code_type_display()})"

    def get_absolute_url(self):
        return reverse('mission_detail', kwargs={'pk': self.pk})
