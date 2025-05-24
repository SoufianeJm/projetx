from django import forms
from .models import Resource, Mission

class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ['full_name', 'picture', 'matricule', 'rate_ibm', 'rate_des', 'rank']

class MissionForm(forms.ModelForm):
    class Meta:
        model = Mission
        fields = ['otp_l2', 'belgian_name', 'comment'] 