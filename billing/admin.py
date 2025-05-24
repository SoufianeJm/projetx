from django.contrib import admin
from .models import Resource, Mission

class MissionAdmin(admin.ModelAdmin):
    list_display = ('otp_l2', 'libelle_de_projet', 'belgian_name', 'code_type')
    list_filter = ('code_type',)
    search_fields = ('otp_l2', 'libelle_de_projet', 'belgian_name')

# Register your models here.
admin.site.register(Resource)
admin.site.register(Mission, MissionAdmin)
