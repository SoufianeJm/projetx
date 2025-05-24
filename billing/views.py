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
    processing_logs = []  # Always available in context
    form = SLRFileUploadForm()

    if request.method == 'POST':
        form = SLRFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            mafe_file_obj = request.FILES['mafe_report_file']
            heures_ibm_file_obj = request.FILES['heures_ibm_file']
            processing_logs.append(f"INFO: File '{mafe_file_obj.name}' uploaded successfully.")
            processing_logs.append(f"INFO: File '{heures_ibm_file_obj.name}' uploaded successfully.")
            try:
                processing_logs.append(f"INFO: Attempting to read data from '{heures_ibm_file_obj.name}'...")
                df_heures_ibm = pd.read_excel(heures_ibm_file_obj)
                processing_logs.append(f"INFO: Data extracted successfully from file '{heures_ibm_file_obj.name}'.")
                if not df_heures_ibm.empty:
                    sample_row_html = df_heures_ibm.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)
                    processing_logs.append(f"INFO: Sample data (first row) from '{heures_ibm_file_obj.name}':<div class='log-table-sample'>{sample_row_html}</div>")
                else:
                    processing_logs.append(f"WARNING: File '{heures_ibm_file_obj.name}' was empty after reading or no data matched expected columns.")
                # Check required columns (from main.py logic)
                required_mafe_cols = ['Country', 'Customer Name']
                required_heures_cols = ['Code projet', 'Nom', 'Grade', 'Date', 'Heures']
                missing_mafe = [col for col in required_mafe_cols if col not in df_mafe.columns]
                missing_heures = [col for col in required_heures_cols if col not in df_heures.columns]
                if missing_mafe or missing_heures:
                    msg = "Missing columns: "
                    if missing_mafe:
                        msg += f"MAFE: {', '.join(missing_mafe)}. "
                    if missing_heures:
                        msg += f"Heures: {', '.join(missing_heures)}."
                    messages.error(request, msg)
                    return render(request, 'billing/facturation_slr.html', {'form': form})

                # --- Main logic (adapted from main.py, ignoring traitement file) ---
                # Clean up columns
                df_heures['Nom'] = df_heures['Nom'].astype(str).str.lower().str.strip()
                df_heures['Heures'] = pd.to_numeric(df_heures['Heures'], errors='coerce').fillna(0)

                # Group by project, name, grade, and sum hours
                employee_summary = (
                    df_heures.groupby(['Code projet', 'Nom', 'Grade'], as_index=False)
                    .agg({'Heures': 'sum'})
                    .rename(columns={'Heures': 'Total Heures'})
                )

                # Merge with MAFE to get project names
                # (Assume 'Customer Name' in MAFE matches 'Code projet' in heures)
                merged = employee_summary.merge(df_mafe[['Country', 'Customer Name']], left_on='Code projet', right_on='Customer Name', how='left')

                # Prepare output
                output_df = merged[['Code projet', 'Nom', 'Grade', 'Total Heures', 'Country', 'Customer Name']]
                output_filename = f'SLR_Report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                output_path = os.path.join('media', 'reports', output_filename)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                output_df.to_excel(output_path, index=False)

                with open(output_path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    response['Content-Disposition'] = f'attachment; filename="{output_filename}"'
                    return response
            except Exception as e:
                error_message = f"ERROR: An processing error occurred: {str(e)}"
                messages.error(request, error_message)
                processing_logs.append(error_message)
        else:
            processing_logs.append("ERROR: Form validation failed. Please check the uploaded files.")
    context = {
        'form': form,
        'page_title': 'Facturation SLR',
        'processing_logs': processing_logs
    }
    return render(request, 'billing/facturation_slr.html', context)
