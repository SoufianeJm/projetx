from django.db import models
from django.urls import reverse

# Create your models here.

class Resource(models.Model):
    # Choices for 'grade' (formerly 'rank')
    GRADE_FR_JSA = 'FR_JSA'
    GRADE_FR_MGR = 'FR_MGR'
    GRADE_FR_NEP = 'FR_NEP'
    GRADE_FR_SMGR = 'FR_SMGR'
    GRADE_FR_SRS = 'FR_SRS'
    GRADE_FR_STF = 'FR_STF'
    GRADE_CHOICES = [
        (GRADE_FR_JSA, 'FR_Junior Staff / Analyst'),
        (GRADE_FR_MGR, 'FR_Manager'),
        (GRADE_FR_NEP, 'FR_Non Equity Partner'),
        (GRADE_FR_SMGR, 'FR_Senior Manager'),
        (GRADE_FR_SRS, 'FR_Senior Staff'),
        (GRADE_FR_STF, 'FR_Staff'),
    ]

    # Choices for 'grade_des'
    GRADE_DES_M3 = 'DES_M3'
    GRADE_DES_M2 = 'DES_M2'
    GRADE_DES_M1 = 'DES_M1'
    GRADE_DES_SC3 = 'DES_SC3'
    GRADE_DES_SC2 = 'DES_SC2'
    GRADE_DES_SC1 = 'DES_SC1'
    GRADE_DES_C2 = 'DES_C2'
    GRADE_DES_CJ = 'DES_CJ'
    GRADE_DES_STG = 'DES_STG'
    GRADE_DES_NA = 'DES_NA'
    GRADE_DES_CHOICES = [
        (GRADE_DES_M3, 'Manager 3'),
        (GRADE_DES_M2, 'Manager 2'),
        (GRADE_DES_M1, 'Manager 1'),
        (GRADE_DES_SC3, 'Senior Consultant 3'),
        (GRADE_DES_SC2, 'Senior Consultant 2'),
        (GRADE_DES_SC1, 'Senior Consultant 1'),
        (GRADE_DES_C2, 'Consultant 2'),
        (GRADE_DES_CJ, 'Consultant Junior'),
        (GRADE_DES_STG, 'Stagiaire'),
        (GRADE_DES_NA, 'N/A'),
    ]

    full_name = models.CharField(max_length=255, verbose_name="Full Name")
    picture = models.ImageField(upload_to='resources/', null=True, blank=True, verbose_name="Profile Picture")
    matricule = models.CharField(max_length=50, unique=True, verbose_name="Matricule")
    grade = models.CharField(
        max_length=10,
        choices=GRADE_CHOICES,
        default=GRADE_FR_STF,
        verbose_name="Grade",
        blank=False,
        null=False
    )
    grade_des = models.CharField(
        max_length=10,
        choices=GRADE_DES_CHOICES,
        default=GRADE_DES_STG,
        verbose_name="Grade DES",
        blank=False,
        null=False
    )
    rate_ibm = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Rate IBM")
    rate_des = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Rate DES")

    def __str__(self):
        return self.full_name

    def get_absolute_url(self):
        try:
            return reverse('resource_detail', kwargs={'pk': self.pk})
        except:
            try:
                return reverse('resource_update', kwargs={'pk': self.pk})
            except:
                return reverse('home')

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
