from django.contrib import admin
from .models import Resource, Mission

class ResourceAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'matricule', 'grade', 'grade_des', 'rate_ibm', 'rate_des')
    list_filter = ('grade', 'grade_des',)
    search_fields = ('full_name', 'matricule')

class MissionAdmin(admin.ModelAdmin):
    list_display = ('otp_l2', 'belgian_name', 'libelle_de_projet', 'code_type')
    list_filter = ('code_type',)
    search_fields = ('otp_l2', 'belgian_name', 'libelle_de_projet')

# Register your models here.
admin.site.register(Resource, ResourceAdmin)
admin.site.register(Mission, MissionAdmin)
