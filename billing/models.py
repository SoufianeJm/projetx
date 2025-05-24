from django.db import models
from django.urls import reverse

# Create your models here.

class Resource(models.Model):
    full_name = models.CharField(max_length=255, verbose_name="Full Name")
    picture = models.ImageField(upload_to='resource_pictures/', blank=True, null=True, verbose_name="Picture")
    matricule = models.CharField(max_length=50, unique=True, verbose_name="Matricule")
    rate_ibm = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Rate IBM")
    rate_des = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Rate DES")
    rank = models.CharField(max_length=100, verbose_name="Rank")

    def __str__(self):
        return self.full_name

    def get_absolute_url(self):
        return reverse('resource_detail', kwargs={'pk': self.pk})

class Mission(models.Model):
    otp_l2 = models.CharField(max_length=100, unique=True, verbose_name="OTP L2 (Swift Code)")
    belgian_name = models.CharField(max_length=255, verbose_name="Belgian Name")
    comment = models.TextField(blank=True, null=True, verbose_name="Comment")

    def __str__(self):
        return f"{self.otp_l2} - {self.belgian_name}"

    def get_absolute_url(self):
        return reverse('mission_detail', kwargs={'pk': self.pk})
