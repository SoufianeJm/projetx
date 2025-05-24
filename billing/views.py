from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Resource, Mission
from .forms import ResourceForm, MissionForm, SLRFileUploadForm
import pandas as pd
import re
from io import BytesIO
from django.http import HttpResponse
from datetime import datetime
from django.contrib import messages
import os

# Create your views here.

@login_required
def home(request):
    return render(request, 'billing/home.html')

@login_required
def resource_list_view(request):
    resources = Resource.objects.all()
    context = {
        'resources': resources,
        'page_title': 'Resources'
    }
    return render(request, 'billing/resource_list.html', context)

@login_required
def mission_list_view(request):
    missions = Mission.objects.all()
    context = {
        'missions': missions,
        'page_title': 'Missions'
    }
    return render(request, 'billing/mission_list.html', context)

@login_required
def resource_create(request):
    if request.method == 'POST':
        form = ResourceForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Resource added successfully!')
            return redirect('resource_list')
    else:
        form = ResourceForm()
    return render(request, 'billing/resource_form.html', {'form': form, 'action': 'Create'})

@login_required
def resource_update(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    if request.method == 'POST':
        form = ResourceForm(request.POST, request.FILES, instance=resource)
        if form.is_valid():
            form.save()
            messages.success(request, 'Resource updated successfully!')
            return redirect('resource_list')
    else:
        form = ResourceForm(instance=resource)
    return render(request, 'billing/resource_form.html', {'form': form, 'action': 'Update'})

@login_required
def resource_delete(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    if request.method == 'POST':
        resource.delete()
        messages.success(request, 'Resource deleted successfully!')
        return redirect('resource_list')
    return render(request, 'billing/resource_confirm_delete.html', {'resource': resource})

@login_required
def mission_create(request):
    if request.method == 'POST':
        form = MissionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mission added successfully!')
            return redirect('mission_list')
    else:
        form = MissionForm()
    return render(request, 'billing/mission_form.html', {'form': form, 'action': 'Create'})

@login_required
def mission_update(request, pk):
    mission = get_object_or_404(Mission, pk=pk)
    if request.method == 'POST':
        form = MissionForm(request.POST, instance=mission)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mission updated successfully!')
            return redirect('mission_list')
    else:
        form = MissionForm(instance=mission)
    return render(request, 'billing/mission_form.html', {'form': form, 'action': 'Update'})

@login_required
def mission_delete(request, pk):
    mission = get_object_or_404(Mission, pk=pk)
    if request.method == 'POST':
        mission.delete()
        messages.success(request, 'Mission deleted successfully!')
        return redirect('mission_list')
    return render(request, 'billing/mission_confirm_delete.html', {'mission': mission})

@login_required
def facturation_slr(request):
    if request.method == 'POST':
        form = SLRFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            mafe_report_file = request.FILES['mafe_report_file']
            heures_ibm_file = request.FILES['heures_ibm_file']
            
            # Read the MAFE report
            df_mafe = pd.read_excel(mafe_report_file)
            
            # Read the heures IBM file
            df_heures = pd.read_excel(heures_ibm_file)
            
            # Get resources from database
            db_resources_data = []
            for r in Resource.objects.all():
                db_resources_data.append({
                    'Nom Complet DB': str(r.full_name).lower().strip(),
                    'Rank DB': r.get_grade_display(),
                    'Grade DES DB': r.get_grade_des_display(),
                    'Rate IBM DB': r.rate_ibm,
                    'Rate DES DB': r.rate_des
                })
            db_resources = pd.DataFrame(db_resources_data)
            
            # Get missions from database
            db_missions_data = []
            for m in Mission.objects.all():
                db_missions_data.append({
                    'OTP L2 DB': m.otp_l2,
                    'Libellé Projet DB': m.libelle_de_projet or m.belgian_name
                })
            db_missions = pd.DataFrame(db_missions_data)
            
            # Process the data
            df_mafe['Nom Complet'] = df_mafe['Nom Complet'].str.lower().str.strip()
            df_heures['Nom Complet'] = df_heures['Nom Complet'].str.lower().str.strip()
            
            # Merge hours data
            df_agg_hours = df_heures.groupby(['Nom Complet', 'OTP L2'])['Heures'].sum().reset_index()
            
            # Merge with database resources
            final_df = pd.merge(df_agg_hours, db_resources, left_on='Nom Complet', right_on='Nom Complet DB', how='left')
            
            # Merge with database missions
            final_df = pd.merge(final_df, db_missions, left_on='OTP L2', right_on='OTP L2 DB', how='left')
            
            # Calculate totals
            final_df['Total IBM'] = final_df['Heures'] * final_df['Rate IBM DB']
            final_df['Total DES'] = final_df['Heures'] * final_df['Rate DES DB']
            
            # Prepare output
            output_df = final_df[[
                'Libellé Projet DB',
                'Nom Complet',
                'Rank DB',
                'Total Heures',
                'Rate DES DB',
                'Rate IBM DB',
                'Total IBM',
                'Total DES'
            ]]
            
            output_df.columns = [
                'Libellé Projet',
                'Full Name (from file)',
                'Rank',
                'Total Heures',
                'Rate DES',
                'Rate IBM',
                'Total IBM',
                'Total DES'
            ]
            
            # Fill NaN values
            output_df[['Rank', 'Rate DES', 'Rate IBM', 'Total IBM', 'Total DES']] = \
                output_df[['Rank', 'Rate DES', 'Rate IBM', 'Total IBM', 'Total DES']].fillna(0)
            
            # Generate Excel file
            output_filename = f'SLR_Report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            output_path = os.path.join('media', 'reports', output_filename)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            output_df.to_excel(output_path, index=False)
            
            # Return the file
            with open(output_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename="{output_filename}"'
                messages.info(request, 'SLR report generated!')
                return response
    else:
        form = SLRFileUploadForm()
    return render(request, 'billing/facturation_slr.html', {'form': form})
