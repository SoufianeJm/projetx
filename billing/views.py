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
from django.db import models
import json
from django.core.serializers.json import DjangoJSONEncoder

# Create your views here.

@login_required
def home(request):
    return render(request, 'billing/home.html')

@login_required
def resource_list_view(request):
    search_query = request.GET.get('search', '')
    resources = Resource.objects.all()
    
    if search_query:
        resources = resources.filter(
            models.Q(full_name__icontains=search_query) |
            models.Q(matricule__icontains=search_query) |
            models.Q(grade__icontains=search_query) |
            models.Q(grade_des__icontains=search_query)
        )
    
    context = {
        'resources': resources,
        'page_title': 'Resources',
        'search_query': search_query
    }
    return render(request, 'billing/resource_list.html', context)

@login_required
def mission_list_view(request):
    search_query = request.GET.get('search', '')
    missions = Mission.objects.all()
    
    if search_query:
        missions = missions.filter(
            models.Q(otp_l2__icontains=search_query) |
            models.Q(belgian_name__icontains=search_query) |
            models.Q(libelle_de_projet__icontains=search_query) |
            models.Q(code_type__icontains=search_query)
        )
    
    context = {
        'missions': missions,
        'page_title': 'Missions',
        'search_query': search_query
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
def mission_calculation_tracking_view(request):
    missions = Mission.objects.all().order_by('belgian_name')
    context = {
        'missions': missions,
        'page_title': 'Suivi Calculs Missions'
    }
    return render(request, 'billing/mission_calculation_tracking.html', context)

def find_otp_l2_column(df):
    def normalize(col):
        return re.sub(r'[\s\u00A0]+', '', str(col)).lower()
    for col in df.columns:
        if normalize(col) == 'otpl2':
            return col
    return None

@login_required
def facturation_slr(request):
    processing_logs = []
    form = SLRFileUploadForm()

    if request.method == 'POST':
        form = SLRFileUploadForm(request.POST, request.FILES)
        heures_ibm_file_obj = request.FILES.get('heures_ibm_file')
        mafe_file_obj = request.FILES.get('mafe_report_file')
        selected_libelle_projet = request.POST.getlist('selected_libelle_projet')

        # 1. Modal trigger: show modal with all candidate missions
        if heures_ibm_file_obj and not selected_libelle_projet:
            try:
                heures_ibm_file_obj.seek(0)
                base_df = pd.read_excel(heures_ibm_file_obj, sheet_name='base')
                otp_col = find_otp_l2_column(base_df)
                if not otp_col:
                    processing_logs.append("ERROR: Could not find 'OTP L2' column in the Heures IBM file.")
                    context = {
                        'form': form,
                        'missions': [],
                        'show_modal': False,
                        'processing_logs': processing_logs,
                        'page_title': 'Facturation SLR',
                    }
                    return render(request, 'billing/facturation_slr.html', context)
                unique_codes = base_df[otp_col].dropna().unique().tolist()
                missions_from_heures_file = Mission.objects.filter(otp_l2__in=unique_codes)
                unique_libelles = sorted(set(m.libelle_de_projet for m in missions_from_heures_file if m.libelle_de_projet))
                context = {
                    'form': form,
                    'missions': unique_libelles,
                    'show_modal': True,
                    'processing_logs': processing_logs,
                    'page_title': 'Facturation SLR',
                }
                return render(request, 'billing/facturation_slr.html', context)
            except Exception as e:
                processing_logs.append(f"ERROR: Could not parse missions from Heures IBM file: {str(e)}")
                context = {
                    'form': form,
                    'missions': [],
                    'show_modal': False,
                    'processing_logs': processing_logs,
                    'page_title': 'Facturation SLR',
                }
                return render(request, 'billing/facturation_slr.html', context)

        # 2. Modal submit: determine target missions for adjustment
        target_mission_libelles_for_adjustment = []
        if heures_ibm_file_obj and selected_libelle_projet is not None:
            heures_ibm_file_obj.seek(0)
            base_df = pd.read_excel(heures_ibm_file_obj, sheet_name='base')
            otp_col = find_otp_l2_column(base_df)
            unique_codes = base_df[otp_col].dropna().unique().tolist()
            missions_from_heures_file = Mission.objects.filter(otp_l2__in=unique_codes)
            all_candidate_libelles = sorted(set(m.libelle_de_projet for m in missions_from_heures_file if m.libelle_de_projet))
            user_selected_libelles = selected_libelle_projet
            if user_selected_libelles:
                target_mission_libelles_for_adjustment = user_selected_libelles
                processing_logs.append(f"INFO: User selected missions for adjustment: {user_selected_libelles}")
            else:
                target_mission_libelles_for_adjustment = all_candidate_libelles
                processing_logs.append("INFO: No missions selected in modal, so all eligible missions will be adjusted: " + str(all_candidate_libelles))

            # ... (rest of your calculation logic) ...
            # For demonstration, let's show how the adjustment mask would be used:
            # (Assume adjusted_df is already created and has 'Libelle projet' column)
            # adjusted_df['final_coeff'] = 0.0
            # adjustment_mask = adjusted_df['Libelle projet'].isin(target_mission_libelles_for_adjustment)
            # adjusted_df.loc[adjustment_mask, 'final_coeff'] = (
            #     adjusted_df.loc[adjustment_mask, 'coeff_total'] *
            #     adjusted_df.loc[adjustment_mask, 'priority_coeff']
            # )

            # 4. Comment out Excel output, just re-render template with logs/results
            context = {
                'form': form,
                'missions': all_candidate_libelles,
                'show_modal': False,
                'processing_logs': processing_logs,
                'page_title': 'Facturation SLR',
            }
            return render(request, 'billing/facturation_slr.html', context)

        # fallback for GET or other cases
    context = {
        'form': form,
        'page_title': 'Facturation SLR',
        'processing_logs': processing_logs,
        'missions': [],
        'show_modal': False,
    }
    return render(request, 'billing/facturation_slr.html', context)

@login_required
def mission_bulk_delete(request):
    if request.method == 'POST':
        try:
            selected_missions = request.POST.getlist('selected_missions')
            print(f"DEBUG: Received POST request for bulk delete. Selected missions: {selected_missions}")
            
            if not selected_missions:
                print("DEBUG: No missions selected for deletion")
                messages.warning(request, 'No missions were selected for deletion.')
                return redirect('mission_list')
            
            # Verify the missions exist before deletion
            existing_missions = Mission.objects.filter(id__in=selected_missions)
            print(f"DEBUG: Found {existing_missions.count()} existing missions to delete")
            
            if existing_missions.exists():
                existing_missions.delete()
                print(f"DEBUG: Successfully deleted {existing_missions.count()} missions")
                messages.success(request, f'Successfully deleted {existing_missions.count()} mission(s).')
            else:
                print("DEBUG: No existing missions found to delete")
                messages.warning(request, 'No valid missions were found to delete.')
        except Exception as e:
            print(f"ERROR: Exception during bulk delete: {str(e)}")
            messages.error(request, f'An error occurred while deleting missions: {str(e)}')
    else:
        print("DEBUG: Non-POST request received for bulk delete")
        messages.warning(request, 'Invalid request method.')
    
    return redirect('mission_list')