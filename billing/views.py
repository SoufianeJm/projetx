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
        selected_libelle_projet = request.POST.getlist('selected_libelle_projet')

        # Debug: log all files in request.FILES
        processing_logs.append('FILES received: ' + ', '.join(f'{k}: {v.name}' for k, v in request.FILES.items()))

        # Only require files if this is the first POST (no missions selected yet)
        if not selected_libelle_projet:
            heures_ibm_file_obj = request.FILES.get('heures_ibm_file')
            mafe_file_obj = request.FILES.get('mafe_report_file')

            # Log file upload status
            if heures_ibm_file_obj:
                processing_logs.append("INFO: Heures IBM file uploaded: {}".format(heures_ibm_file_obj.name))
            else:
                processing_logs.append("ERROR: No Heures IBM file uploaded.")
            if mafe_file_obj:
                processing_logs.append("INFO: MAFE report file uploaded: {}".format(mafe_file_obj.name))
            else:
                processing_logs.append("ERROR: No MAFE report file uploaded.")

            # Check if both files are present
            if not (heures_ibm_file_obj and mafe_file_obj):
                processing_logs.append("ERROR: Both Heures IBM and MAFE report files are required.")
                context = {
                    'form': form,
                    'missions': [],
                    'show_modal': False,
                    'processing_logs': processing_logs,
                    'page_title': 'Facturation SLR',
                }
                return render(request, 'billing/facturation_slr.html', context)

            # 1. Modal trigger: show modal with all candidate missions
            try:
                # Process Heures IBM file
                heures_ibm_file_obj.seek(0)
                base_df = pd.read_excel(heures_ibm_file_obj, sheet_name='base')
                processing_logs.append(f"INFO: Heures IBM file parsed. base_df shape: {base_df.shape}")
                
                # Process MAFE report file EXACTLY like main.py
                mafe_file_obj.seek(0)
                mafe_raw = pd.read_excel(mafe_file_obj, sheet_name='(Tab A) FULLY COMMITTED', header=None)
                mafe_raw.columns = mafe_raw.iloc[14].astype(str).str.strip().str.replace('\n', ' ').str.replace('\r', ' ')
                mafe_df = mafe_raw.drop(index=list(range(0, 15))).reset_index(drop=True)
                processing_logs.append(f"INFO: MAFE report file parsed. mafe_df shape: {mafe_df.shape}")

                # Get OTP L2 column in base_df
                otp_col = find_otp_l2_column(base_df)
                if not otp_col:
                    raise ValueError("Could not find 'OTP L2' column in the Heures IBM file")

                # Find the 'Customer Name' column in mafe_df
                processing_logs.append(f"mafe_df columns: {list(mafe_df.columns)}")
                def normalize(col):
                    return re.sub(r'[\s\u00A0_]+', '', str(col)).lower()
                mafe_customer_col = None
                for col in mafe_df.columns:
                    if normalize(col) == 'customername':
                        mafe_customer_col = col
                        break
                if not mafe_customer_col:
                    raise ValueError("Could not find 'Customer Name' column in the MAFE file")
                processing_logs.append(f"INFO: Using '{otp_col}' from base_df and '{mafe_customer_col}' from mafe_df for merge.")

                # Find the corresponding column in base_df (try 'Customer Name' or fallback to otp_col)
                base_customer_col = None
                for col in base_df.columns:
                    if normalize(col) == 'customername':
                        base_customer_col = col
                        break
                if not base_customer_col:
                    base_customer_col = otp_col  # fallback

                # Get unique codes and get missions
                unique_codes = base_df[otp_col].dropna().unique().tolist()
                processing_logs.append(f"INFO: Unique OTP L2 codes extracted: {unique_codes}")
                missions_from_heures_file = Mission.objects.filter(otp_l2__in=unique_codes)
                unique_libelles = sorted(set(m.libelle_de_projet for m in missions_from_heures_file if m.libelle_de_projet))
                processing_logs.append(f"INFO: Candidate missions for adjustment (libelle_de_projet): {unique_libelles}")

                # Store DataFrames in session for later use
                request.session['base_df'] = base_df.to_json()
                request.session['mafe_df'] = mafe_df.to_json()
                print("DEBUG: base_df and mafe_df stored in session")

                context = {
                    'form': form,
                    'missions': unique_libelles,
                    'show_modal': True,
                    'processing_logs': processing_logs,
                    'page_title': 'Facturation SLR',
                }
                return render(request, 'billing/facturation_slr.html', context)
            except Exception as e:
                processing_logs.append(f"ERROR: Could not parse files: {str(e)}<br><pre>{traceback.format_exc()}</pre>")
                context = {
                    'form': form,
                    'missions': [],
                    'show_modal': False,
                    'processing_logs': processing_logs,
                    'page_title': 'Facturation SLR',
                }
                return render(request, 'billing/facturation_slr.html', context)
        else:
            # Second POST: do NOT require files, use DataFrames from session
            print("DEBUG: base_df in session:", 'base_df' in request.session)
            print("DEBUG: mafe_df in session:", 'mafe_df' in request.session)
            # 2. Modal submit: determine target missions for adjustment
            target_mission_libelles_for_adjustment = []
            try:
                # Retrieve DataFrames from session
                base_df = pd.read_json(request.session.get('base_df', '{}'))
                mafe_df = pd.read_json(request.session.get('mafe_df', '{}'))
                
                if base_df.empty or mafe_df.empty:
                    raise ValueError("Session data for DataFrames is missing or invalid")

                processing_logs.append(f"INFO: Retrieved DataFrames from session. base_df shape: {base_df.shape}, mafe_df shape: {mafe_df.shape}")

                # Get OTP L2 column in base_df
                otp_col = find_otp_l2_column(base_df)
                if not otp_col:
                    raise ValueError("Could not find 'OTP L2' column in the Heures IBM file")

                # Find the 'Customer Name' column in mafe_df
                processing_logs.append(f"mafe_df columns: {list(mafe_df.columns)}")
                def normalize(col):
                    return re.sub(r'[\s\u00A0_]+', '', str(col)).lower()
                mafe_customer_col = None
                for col in mafe_df.columns:
                    if normalize(col) == 'customername':
                        mafe_customer_col = col
                        break
                if not mafe_customer_col:
                    raise ValueError("Could not find 'Customer Name' column in the MAFE file")
                processing_logs.append(f"INFO: Using '{otp_col}' from base_df and '{mafe_customer_col}' from mafe_df for merge.")

                # Find the corresponding column in base_df (try 'Customer Name' or fallback to otp_col)
                base_customer_col = None
                for col in base_df.columns:
                    if normalize(col) == 'customername':
                        base_customer_col = col
                        break
                if not base_customer_col:
                    base_customer_col = otp_col  # fallback

                # Get unique codes and missions
                unique_codes = base_df[otp_col].dropna().unique().tolist()
                missions_from_heures_file = Mission.objects.filter(otp_l2__in=unique_codes)
                all_candidate_libelles = sorted(set(m.libelle_de_projet for m in missions_from_heures_file if m.libelle_de_projet))
                
                # Handle mission selection
                user_selected_libelles = selected_libelle_projet
                processing_logs.append(f"INFO: user_selected_libelles from modal: {user_selected_libelles}")
                
                if user_selected_libelles:
                    target_mission_libelles_for_adjustment = user_selected_libelles
                    processing_logs.append(f"INFO: User selected missions for adjustment: {user_selected_libelles}")
                else:
                    target_mission_libelles_for_adjustment = all_candidate_libelles
                    processing_logs.append(f"INFO: No missions selected in modal, so all eligible missions will be adjusted: {all_candidate_libelles}")
                
                processing_logs.append(f"INFO: Final target_mission_libelles_for_adjustment: {target_mission_libelles_for_adjustment}")

                # --- Begin Calculation Logic ---
                # Merge Heures IBM and MAFE data on 'Customer Name'
                merged_df = pd.merge(
                    base_df,
                    mafe_df,
                    left_on=base_customer_col,
                    right_on=mafe_customer_col,
                    how='left'
                )
                processing_logs.append(f"INFO: Merged DataFrames shape: {merged_df.shape}")

                # Create adjusted DataFrame
                adjusted_df = merged_df.copy()
                
                # Ensure required columns exist
                required_cols = ['Libelle projet', 'Total Heures', 'Rate', 'Total_Projet_Cout', 'total_rate_proj', 'coeff_total', 'priority_coeff']
                for col in required_cols:
                    if col not in adjusted_df.columns:
                        adjusted_df[col] = 1.0
                
                # Set Libelle projet column
                adjusted_df['Libelle projet'] = adjusted_df['Libelle projet'] if 'Libelle projet' in adjusted_df.columns else adjusted_df[otp_col].astype(str)

                # Log shape before adjustment
                processing_logs.append(f"INFO: adjusted_df shape before adjustment: {adjusted_df.shape}")

                # Conditional adjustment logic
                adjusted_df['final_coeff'] = 0.0
                adjustment_mask = adjusted_df['Libelle projet'].isin(target_mission_libelles_for_adjustment)
                valid_mask = (adjusted_df['Total_Projet_Cout'] > 0) & (adjusted_df['total_rate_proj'] > 0)
                full_mask = adjustment_mask & valid_mask
                
                adjusted_df.loc[full_mask, 'final_coeff'] = (
                    adjusted_df.loc[full_mask, 'coeff_total'] * 
                    adjusted_df.loc[full_mask, 'priority_coeff']
                )

                # Calculate adjusted values
                adjusted_df['Adjusted Hours'] = adjusted_df['Total Heures'] * adjusted_df['final_coeff']
                adjusted_df['Adjusted Cost'] = adjusted_df['Total_Projet_Cout'] * adjusted_df['final_coeff']

                # Log DataFrame sample after adjustment
                sample_cols = ['Libelle projet', 'Total Heures', 'Rate', 'Total_Projet_Cout', 'total_rate_proj', 'coeff_total', 'priority_coeff', 'final_coeff', 'Adjusted Hours', 'Adjusted Cost']
                sample_cols = [c for c in sample_cols if c in adjusted_df.columns]
                processing_logs.append("<b>Sample of adjusted_df after final_coeff calculation:</b><div class='log-table-sample'>" + adjusted_df[sample_cols].head(8).to_html(index=False) + "</div>")

                # Debug: log columns before groupby
                processing_logs.append(f"base_df columns: {list(base_df.columns)}")
                processing_logs.append(f"adjusted_df columns: {list(adjusted_df.columns)}")

                # --- Excel Output Block ---
                try:
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        # Write original data
                        base_df.to_excel(writer, index=False, sheet_name='01_HeuresIBM_Base')
                        mafe_df.to_excel(writer, index=False, sheet_name='01_MAFE_Report')

                        # Create and write summaries (match main.py)
                        # Employee summary
                        employee_summary_df = adjusted_df.groupby(['Libelle projet', 'Nom', 'Grade'], as_index=False).agg({
                            'Total Heures': 'sum',
                            'Adjusted Hours': 'sum',
                            'Total_Projet_Cout': 'sum',
                            'Adjusted Cost': 'sum',
                            'Rate': 'first',
                            'priority_coeff': 'first',
                        })
                        # Global summary
                        global_summary_df = adjusted_df.groupby('Libelle projet', as_index=False).agg({
                            'Total Heures': 'sum',
                            'Adjusted Hours': 'sum',
                            'Total_Projet_Cout': 'sum',
                            'Adjusted Cost': 'sum'
                        })

                        employee_summary_df.to_excel(writer, index=False, sheet_name='02_EmployeeSummary')
                        global_summary_df.to_excel(writer, index=False, sheet_name='02_GlobalSummary')

                        # Write adjusted and result data
                        adjusted_df.to_excel(writer, index=False, sheet_name='03_Adjusted')
                        result_df = adjusted_df[['Libelle projet', 'Total Heures', 'Adjusted Hours', 'Total_Projet_Cout', 'Adjusted Cost']]
                        result_df.to_excel(writer, index=False, sheet_name='04_Result')

                    output.seek(0)
                    now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"SLR_Facturation_{now_str}.xlsx"
                    processing_logs.append(f"INFO: Excel file generated with sheets: 01_HeuresIBM_Base, 01_MAFE_Report, 02_EmployeeSummary, 02_GlobalSummary, 03_Adjusted, 04_Result")

                    response = HttpResponse(
                        output.getvalue(),
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response
                except Exception as e:
                    processing_logs.append(f"ERROR: Failed to generate Excel file: {str(e)}<br><pre>{traceback.format_exc()}</pre>")
                    # Fall through to render logs

                # --- End Excel Output Block ---

                context = {
                    'form': form,
                    'missions': all_candidate_libelles,
                    'show_modal': False,
                    'processing_logs': processing_logs,
                    'page_title': 'Facturation SLR',
                }
                return render(request, 'billing/facturation_slr.html', context)
            except Exception as e:
                processing_logs.append(f"ERROR: Exception during calculation: {str(e)}<br><pre>{traceback.format_exc()}</pre>")
                context = {
                    'form': form,
                    'missions': [],
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