from django import forms
from .models import Resource, Mission

class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ['full_name', 'picture', 'matricule', 'grade', 'grade_des', 'rate_ibm', 'rate_des']

class MissionForm(forms.ModelForm):
    class Meta:
        model = Mission
        fields = ['otp_l2', 'belgian_name', 'libelle_de_projet', 'code_type']

class SLRFileUploadForm(forms.Form):
    mafe_report_file = forms.FileField(
        label='DTT IMT France MAFE Report (xlsx)',
        help_text='e.g., DTT IMT France MAFE Report - Mai 2024.xlsx'
    )
    heures_ibm_file = forms.FileField(
        label='Heures IBM (xlsx)',
        help_text='e.g., Heures IBM Mai 25.xlsx'
    ) 