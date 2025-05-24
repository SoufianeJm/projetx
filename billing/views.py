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
import traceback

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
    processing_logs = []
    form = SLRFileUploadForm()

    if request.method == 'POST':
        form = SLRFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            mafe_file_obj = request.FILES['mafe_report_file']
            heures_ibm_file_obj = request.FILES['heures_ibm_file']
            processing_logs.append(f"INFO: File '{mafe_file_obj.name}' received for processing.")
            processing_logs.append(f"INFO: File '{heures_ibm_file_obj.name}' received for processing.")
            try:
                # --- Parse Heures IBM Filename (Month/Year) ---
                heures_filename = heures_ibm_file_obj.name
                mois_mapping = {
                    'Janvier': 'Jan', 'Février': 'Feb', 'Mars': 'Mar', 'Avril': 'Apr', 'Mai': 'May', 'Juin': 'Jun',
                    'Juillet': 'Jul', 'Août': 'Aug', 'Septembre': 'Sep', 'Octobre': 'Oct', 'Novembre': 'Nov', 'Décembre': 'Dec',
                    'Jan': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Apr', 'May': 'May', 'Jun': 'Jun',
                    'Jul': 'Jul', 'Aug': 'Aug', 'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dec'
                }
                match = re.search(r'(Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\d]*(\d{2,4})', heures_filename)
                if not match:
                    msg = f"ERROR: Could not parse month/year from Heures IBM filename: {heures_filename}"
                    messages.error(request, msg)
                    processing_logs.append(msg)
                    return render(request, 'billing/facturation_slr.html', {'form': form, 'page_title': 'Facturation SLR', 'processing_logs': processing_logs})
                parsed_mois_nom = match.group(1).capitalize()
                parsed_annee_full = match.group(2)
                processing_logs.append(f"INFO: Parsed period: {parsed_mois_nom} {parsed_annee_full} from '{heures_filename}'.")

                # --- Read "Heures IBM" file ---
                processing_logs.append(f"INFO: Attempting to read data from '{heures_ibm_file_obj.name}'...")
                df_heures_ibm = pd.read_excel(heures_ibm_file_obj, sheet_name='base', usecols="E,H,I,N")
                df_heures_ibm.columns = ['Code projet', 'Nom Complet', 'Grade', 'Heures Déclarées']
                df_heures_ibm['Nom Complet'] = df_heures_ibm['Nom Complet'].astype(str).str.lower().str.strip()
                df_heures_ibm['Heures Déclarées'] = pd.to_numeric(df_heures_ibm['Heures Déclarées'], errors='coerce').fillna(0)
                processing_logs.append(f"INFO: Data extracted successfully from file '{heures_ibm_file_obj.name}'.")
                if not df_heures_ibm.empty:
                    sample_html = df_heures_ibm.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)
                    processing_logs.append(f"INFO: Sample data (first row) from '{heures_ibm_file_obj.name}':<div class='log-table-sample'>{sample_html}</div>")
                else:
                    processing_logs.append(f"WARNING: No data extracted or file '{heures_ibm_file_obj.name}' was empty after applying column names.")

                # --- Read "MAFE Report" file ---
                processing_logs.append(f"INFO: Attempting to read data from '{mafe_file_obj.name}'...")
                mafe_raw_df = pd.read_excel(mafe_file_obj, sheet_name='(Tab A) FULLY COMMITTED', header=None)
                if mafe_raw_df.shape[0] > 14:
                    mafe_columns = mafe_raw_df.iloc[14].astype(str).str.strip().str.replace('\n', ' ', regex=False).str.replace('\r', ' ', regex=False)
                    df_mafe = mafe_raw_df.iloc[15:].copy()
                    df_mafe.columns = mafe_columns
                    df_mafe.reset_index(drop=True, inplace=True)
                    processing_logs.append(f"INFO: Data extracted successfully from file '{mafe_file_obj.name}'.")
                    if not df_mafe.empty:
                        sample_html_mafe = df_mafe.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)
                        processing_logs.append(f"INFO: Sample data (first row) from '{mafe_file_obj.name}':<div class='log-table-sample'>{sample_html_mafe}</div>")
                    else:
                        processing_logs.append(f"WARNING: No data extracted or file '{mafe_file_obj.name}' was empty after header processing.")
                else:
                    processing_logs.append(f"ERROR: File '{mafe_file_obj.name}' does not have enough rows to extract header from row 15.")
                    df_mafe = pd.DataFrame()
                if 'df_mafe' not in locals():
                    processing_logs.append(f"CRITICAL ERROR: df_mafe was not defined after MAFE file processing attempt.")
                    df_mafe = pd.DataFrame()

                # --- Continue with your data processing using df_heures_ibm and df_mafe ---
                processing_logs.append("INFO: Proceeding with data merging and calculations...")
                # ... (your merging/calculation/output logic here) ...
                # For demonstration, just return the logs (remove/comment this in production):
                # return render(request, 'billing/facturation_slr.html', {'form': form, 'page_title': 'Facturation SLR', 'processing_logs': processing_logs})
                # --- End demonstration ---
                # (Uncomment and use your actual Excel generation and response logic below)
                # messages.success(request, "Report generated and download started successfully!")
                # return response
            except Exception as e:
                error_msg = f"ERROR: An unexpected error occurred during processing: {str(e)}"
                processing_logs.append(f"{error_msg}<br><pre>{traceback.format_exc()}</pre>")
                messages.error(request, "An error occurred while generating the report. See logs for details.")
        else:
            processing_logs.append("ERROR: Form validation failed. Please check the uploaded files and try again.")
            for field, errors in form.errors.items():
                for error in errors:
                    processing_logs.append(f"ERROR (Form field: {field}): {error}")

    context = {
        'form': form,
        'page_title': 'Facturation SLR',
        'processing_logs': processing_logs
    }
    return render(request, 'billing/facturation_slr.html', context)
