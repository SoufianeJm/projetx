from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Resource, Mission
from .forms import ResourceForm, MissionForm, SLRFileUploadForm
import pandas as pd
import numpy as np # Import numpy for np.where
import re
from io import BytesIO
from django.http import HttpResponse
from datetime import datetime
from django.contrib import messages
import os
import traceback
from django.db import models

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
                mois = mois_mapping.get(parsed_mois_nom, parsed_mois_nom)
                annee = parsed_annee_full
                processing_logs.append(f"INFO: Parsed period: {parsed_mois_nom} {parsed_annee_full} from '{heures_filename}'.")

                # --- Fetch Resource Data ---
                resources_qs = Resource.objects.all()
                db_resources_df = pd.DataFrame(list(resources_qs.values('full_name', 'grade', 'rate_ibm', 'rate_des')))
                if db_resources_df.empty:
                    processing_logs.append("ERROR: No resources found in the database.")
                    messages.error(request, "Processing Error: No resources found in the database.")
                    return render(request, 'billing/facturation_slr.html', {'form': form, 'page_title': 'Facturation SLR', 'processing_logs': processing_logs})
                db_resources_df['Nom'] = db_resources_df['full_name'].astype(str).str.lower().str.strip()
                # db_resources_df['Grade'] is already correct from model
                db_resources_df['Rate'] = pd.to_numeric(db_resources_df['rate_ibm'], errors='coerce').fillna(0)
                db_resources_df['Rate DES'] = pd.to_numeric(db_resources_df['rate_des'], errors='coerce').fillna(0)
                processing_logs.append(f"INFO: Resource data loaded. Count: {len(db_resources_df)}. Sample:<div class='log-table-sample'>{db_resources_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Fetch Mission Data ---
                missions_qs = Mission.objects.all()
                # Ensure correct field mapping: model.belgian_name is "Libellé de Projet", model.libelle_de_projet is "Belgian Name"
                db_missions_df = pd.DataFrame(list(missions_qs.values('otp_l2', 'belgian_name', 'libelle_de_projet'))) 
                if db_missions_df.empty:
                    processing_logs.append("ERROR: No missions found in the database.")
                    messages.error(request, "Processing Error: No missions found in the database.")
                    return render(request, 'billing/facturation_slr.html', {'form': form, 'page_title': 'Facturation SLR', 'processing_logs': processing_logs})
                db_missions_df.rename(columns={
                    'otp_l2': 'Code projet',
                    'belgian_name': 'Libelle projet', # This is the actual "Libellé de Projet"
                    'libelle_de_projet': 'MAFE Customer Name Match' # This is the "Belgian Name" for MAFE matching
                }, inplace=True)
                db_missions_df['Libelle projet'] = db_missions_df['Libelle projet'].fillna('')
                db_missions_df['MAFE Customer Name Match'] = db_missions_df['MAFE Customer Name Match'].fillna('')
                processing_logs.append(f"INFO: Mission data loaded. Count: {len(db_missions_df)}. Sample:<div class='log-table-sample'>{db_missions_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")
                
                # --- Read Heures IBM file (base_df) ---
                processing_logs.append(f"INFO: Attempting to read data from '{heures_ibm_file_obj.name}'...")
                base_df = pd.read_excel(heures_ibm_file_obj, sheet_name='base', usecols="E,H,I,M,N")
                base_df.columns = ['Code projet', 'Nom', 'Grade_IBM', 'Date', 'Heures'] # Grade from IBM file
                base_df['Nom'] = base_df['Nom'].astype(str).str.lower().str.strip()
                base_df['Heures'] = pd.to_numeric(base_df['Heures'], errors='coerce').fillna(0)
                
                base_df = base_df.merge(db_missions_df[['Code projet', 'Libelle projet']], on='Code projet', how='left')
                base_df['Libelle projet'] = base_df['Libelle projet'].fillna(base_df['Code projet']) # Fallback
                processing_logs.append(f"INFO: Heures IBM data processed. Count: {len(base_df)}. Sample:<div class='log-table-sample'>{base_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Create employee_summary_df ---
                # Group by 'Libelle projet', 'Nom', and 'Grade_IBM' (from Excel file)
                employee_summary_df = (
                    base_df.groupby(['Libelle projet', 'Nom', 'Grade_IBM'], as_index=False) 
                    .agg({'Heures': 'sum'})
                    .rename(columns={'Heures': 'Total Heures', 'Grade_IBM': 'Grade'}) # Rename Grade_IBM to Grade for consistency
                )
                # Merge with Resource for rates. 'Grade' in employee_summary_df is now from IBM file.
                # If you need the DB grade, you'd merge db_resources_df['Grade'] and rename appropriately.
                # For now, 'Grade' in employee_summary will be what was in the IBM file.
                employee_summary_df = employee_summary_df.merge(
                    db_resources_df[['Nom', 'Rate', 'Rate DES']], # Removed 'Grade' from here to avoid conflict if logic changes
                    on='Nom', how='left'
                )
                employee_summary_df['Rate'] = employee_summary_df['Rate'].fillna(0)
                employee_summary_df['Rate DES'] = employee_summary_df['Rate DES'].fillna(0)
                employee_summary_df['Total'] = employee_summary_df['Total Heures'] * employee_summary_df['Rate']
                employee_summary_df['Total DES'] = employee_summary_df['Total Heures'] * employee_summary_df['Rate DES']
                processing_logs.append(f"INFO: Employee summary created. Count: {len(employee_summary_df)}. Sample:<div class='log-table-sample'>{employee_summary_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Read MAFE Report file (df_mafe) ---
                processing_logs.append(f"INFO: Attempting to read data from '{mafe_file_obj.name}'...")
                mafe_raw_df = pd.read_excel(mafe_file_obj, sheet_name='(Tab A) FULLY COMMITTED', header=None)
                df_mafe = pd.DataFrame() 
                if mafe_raw_df.shape[0] > 14:
                    mafe_columns = mafe_raw_df.iloc[14].astype(str).str.strip().str.replace('\n', ' ', regex=False).str.replace('\r', ' ', regex=False)
                    df_mafe = mafe_raw_df.iloc[15:].copy()
                    df_mafe.columns = mafe_columns
                    df_mafe.reset_index(drop=True, inplace=True)
                    processing_logs.append(f"INFO: MAFE Data extracted. Count: {len(df_mafe)}.")
                else:
                    processing_logs.append(f"ERROR: MAFE file '{mafe_file_obj.name}' too short.")
                    messages.error(request, f"Processing Error: MAFE file '{mafe_file_obj.name}' format error (too short).")
                
                # --- Process mafe_subset_df ---
                mafe_subset_df = pd.DataFrame(columns=["Country", "Customer Name", "Libelle projet", "Estimees"]) 
                if not df_mafe.empty:
                    forecast_col_cleaned = next((col for col in df_mafe.columns if mois in col and 'Forecasts' in col and annee[-2:] in col), None)
                    if forecast_col_cleaned:
                        mafe_subset_df = df_mafe[['Country', 'Customer Name', forecast_col_cleaned]].copy()
                        mafe_subset_df.rename(columns={forecast_col_cleaned: 'Estimees'}, inplace=True)
                        
                        # Merge MAFE 'Customer Name' with Mission's 'MAFE Customer Name Match' to get 'Libelle projet'
                        mafe_subset_df = mafe_subset_df.merge(
                            db_missions_df[['MAFE Customer Name Match', 'Libelle projet']],
                            left_on='Customer Name', right_on='MAFE Customer Name Match', how='left'
                        )
                        # Use 'Libelle projet' from mission mapping, fallback to MAFE 'Customer Name'
                        mafe_subset_df['Libelle projet'] = mafe_subset_df['Libelle projet_y'].fillna(mafe_subset_df['Customer Name'])
                        # Drop helper columns: Libelle projet_x (if exists from bad merge), Libelle projet_y, MAFE Customer Name Match
                        mafe_subset_df.drop(columns=[col for col in ['Libelle projet_x', 'Libelle projet_y', 'MAFE Customer Name Match'] if col in mafe_subset_df.columns], inplace=True)
                        processing_logs.append(f"INFO: MAFE subset created. Count: {len(mafe_subset_df)}.")
                    else:
                        processing_logs.append(f"WARNING: Forecast column for {mois} {annee} not found in MAFE file.")
                else:
                     processing_logs.append(f"WARNING: MAFE data is empty, MAFE subset will be empty.")
                processing_logs.append(f"INFO: MAFE subset sample:<div class='log-table-sample'>{mafe_subset_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- summary_by_proj_df ---
                summary_by_proj_df = (
                    employee_summary_df.groupby('Libelle projet', as_index=False)
                    .agg({'Total Heures': 'sum', 'Total': 'sum', 'Total DES': 'sum'})
                )
                processing_logs.append(f"DEBUG: summary_by_proj_df created. Count: {len(summary_by_proj_df)}.")

                # --- global_summary_df ---
                if not mafe_subset_df.empty:
                    global_summary_df = pd.merge(
                        mafe_subset_df[['Libelle projet', 'Estimees']].drop_duplicates(subset=['Libelle projet']),
                        summary_by_proj_df,
                        on='Libelle projet', how='left' 
                    )
                else: # If mafe_subset is empty, global_summary is based on summary_by_proj_df only
                    global_summary_df = summary_by_proj_df.copy()
                    global_summary_df['Estimees'] = 0 # No estimates if MAFE is empty/missing
                
                global_summary_df[['Total Heures', 'Total', 'Total DES']] = global_summary_df[['Total Heures', 'Total', 'Total DES']].fillna(0)
                global_summary_df['Estimees'] = pd.to_numeric(global_summary_df['Estimees'].astype(str).str.strip().replace(['', '-', 'nan', 'None'], '0', regex=False), errors='coerce').fillna(0)
                processing_logs.append(f"DEBUG: global_summary_df created. Count: {len(global_summary_df)}.")

                # --- adjusted_df ---
                adjusted_df = pd.merge(
                    employee_summary_df,
                    global_summary_df[['Libelle projet', 'Estimees']],
                    on='Libelle projet', how='left'
                )
                adjusted_df['Estimees'] = adjusted_df['Estimees'].fillna(0)

                adjusted_df['Total_Projet_Cout'] = adjusted_df.groupby('Libelle projet')['Total'].transform('sum').fillna(0)
                adjusted_df['total_rate_proj'] = adjusted_df.groupby('Libelle projet')['Rate'].transform('sum').fillna(0)
                
                # Initialize columns for coefficients and Adjusted Hours
                adjusted_df['coeff_total'] = np.nan
                adjusted_df['priority_coeff'] = np.nan
                adjusted_df['final_coeff'] = np.nan
                adjusted_df['Adjusted Hours'] = adjusted_df['Total Heures'] # Default to Total Heures

                # Mask for rows where adjustment calculation is possible
                can_calculate_coeffs_mask = (adjusted_df['Total_Projet_Cout'] > 0) & (adjusted_df['total_rate_proj'] > 0)
                
                if can_calculate_coeffs_mask.any():
                    calculable_part = adjusted_df[can_calculate_coeffs_mask].copy()

                    # Calculate raw coeff_total
                    calculable_part['coeff_total'] = calculable_part['Estimees'] / calculable_part['Total_Projet_Cout']
                    calculable_part['priority_coeff'] = calculable_part['Rate'] / calculable_part['total_rate_proj']

                    # Determine effective_coeff_total for final_coeff calculation
                    # If Estimees >= Total_Projet_Cout, effective_coeff_total is 1.0
                    # Otherwise, it's the raw coeff_total.
                    effective_coeff_total = np.where(
                        calculable_part['Estimees'] >= calculable_part['Total_Projet_Cout'],
                        1.0,
                        calculable_part['coeff_total'] 
                    )
                    calculable_part['final_coeff'] = effective_coeff_total * calculable_part['priority_coeff']
                    
                    # Calculate Adjusted Hours
                    calculated_adj_hours = (calculable_part['Total Heures'] * (1 - calculable_part['final_coeff'])).round()
                    calculable_part['Adjusted Hours'] = calculated_adj_hours.apply(lambda x: max(x, 0.0) if pd.notnull(x) else 0.0)
                    
                    # Update the original adjusted_df with calculated values
                    adjusted_df.update(calculable_part)

                # Ensure Adjusted Hours are not negative for all rows (redundant if apply above worked, but safe)
                adjusted_df['Adjusted Hours'] = adjusted_df['Adjusted Hours'].apply(lambda x: max(x, 0.0) if pd.notnull(x) else 0.0)
                
                adjusted_df['Heures Retirées'] = adjusted_df['Total Heures'] - adjusted_df['Adjusted Hours']
                adjusted_df['Adjusted Cost'] = adjusted_df['Adjusted Hours'] * adjusted_df['Rate']
                adjusted_df['ID'] = adjusted_df['Nom'].astype(str) + ' - ' + adjusted_df['Libelle projet'].astype(str)
                
                processing_logs.append(f"DEBUG: adjusted_df calculations complete. Count: {len(adjusted_df)}.")
                if can_calculate_coeffs_mask.any():
                     processing_logs.append(f"DEBUG: adjusted_df sample (calculable part):<div class='log-table-sample'>{adjusted_df[can_calculate_coeffs_mask][['Libelle projet', 'Nom', 'Total Heures', 'Estimees', 'coeff_total', 'priority_coeff', 'final_coeff', 'Adjusted Hours']].head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- result_df ---
                result_df = (
                    adjusted_df.groupby('Libelle projet', as_index=False)
                    .agg({'Total Heures': 'sum', 'Adjusted Hours': 'sum', 'Adjusted Cost': 'sum'})
                    .merge(global_summary_df[['Libelle projet', 'Estimees']].drop_duplicates(subset=['Libelle projet']), on='Libelle projet', how='left')
                )
                result_df['Estimees'] = result_df['Estimees'].fillna(0)
                result_df['Ecart'] = result_df['Estimees'] - result_df['Adjusted Cost']
                processing_logs.append(f"DEBUG: result_df created. Count: {len(result_df)}.")

                # --- Rounding ---
                for df_to_round in [employee_summary_df, global_summary_df, adjusted_df, result_df]:
                    if df_to_round is not None and not df_to_round.empty:
                        for col in df_to_round.select_dtypes(include=np.number).columns:
                            # Check if column is not one of the specific coefficient columns before rounding to 0 for them
                            if col not in ['coeff_total', 'priority_coeff', 'final_coeff']:
                                df_to_round[col] = df_to_round[col].round(0)
                            else: # For coeffs, maybe round to a few decimal places for display
                                df_to_round[col] = df_to_round[col].round(4) 


                # --- Excel Output ---
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    workbook = writer.book
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D2E9', 'border': 1, 'text_wrap': True, 'valign': 'top'})
                    default_cell_format = workbook.add_format({'border': 1, 'valign': 'top'})
                    int_format = workbook.add_format({'num_format': '0', 'border': 1, 'valign': 'top'})
                    float_format_coeffs = workbook.add_format({'num_format': '0.0000', 'border': 1, 'valign': 'top'})


                    def write_excel_sheet_final(df_to_write, sheet_name_excel, selected_cols_excel=None):
                        current_df = df_to_write.copy() # Work on a copy
                        if current_df is None or current_df.empty:
                            processing_logs.append(f"WARNING: DataFrame for sheet '{sheet_name_excel}' is empty. Writing empty sheet message.")
                            empty_df_message = pd.DataFrame([{'Status': f'No data available for {sheet_name_excel}'}])
                            empty_df_message.to_excel(writer, sheet_name=sheet_name_excel, index=False, startrow=1, header=False)
                            ws_empty = writer.sheets[sheet_name_excel]
                            ws_empty.write(0, 0, 'Status', header_format)
                            ws_empty.set_column(0, 0, 50, default_cell_format)
                            return

                        # Handle NaN values
                        for col_nan in current_df.columns:
                            if pd.api.types.is_numeric_dtype(current_df[col_nan]):
                                current_df[col_nan] = current_df[col_nan].fillna(0)
                            else:
                                current_df[col_nan] = current_df[col_nan].fillna("N/A")
                        
                        if selected_cols_excel:
                            final_cols_to_use = [col for col in selected_cols_excel if col in current_df.columns]
                            current_df = current_df[final_cols_to_use]
                        
                        if current_df.empty: # If it became empty after column selection
                            processing_logs.append(f"WARNING: DataFrame for sheet '{sheet_name_excel}' became empty after column selection. Writing empty sheet message.")
                            # (similar empty sheet message as above)
                            return

                        current_df.to_excel(writer, sheet_name=sheet_name_excel, index=False, startrow=1, header=False)
                        ws = writer.sheets[sheet_name_excel]
                        for c_idx, col_name_excel in enumerate(current_df.columns):
                            ws.write(0, c_idx, col_name_excel, header_format)
                            # Column width logic
                            try:
                                max_len_val = current_df[col_name_excel].astype(str).map(len).max() if not current_df.empty else 0
                                col_width = max(len(str(col_name_excel)) + 2, max_len_val + 2, 12) # Min width 12
                                col_width = min(col_width, 50) # Max width 50
                            except:
                                col_width = 20 # Fallback
                            
                            # Cell format
                            cell_fmt = default_cell_format
                            if pd.api.types.is_integer_dtype(current_df[col_name_excel]):
                                cell_fmt = int_format
                            elif col_name_excel in ['coeff_total', 'priority_coeff', 'final_coeff']:
                                cell_fmt = float_format_coeffs
                            elif pd.api.types.is_float_dtype(current_df[col_name_excel]): # Other floats
                                 # Check if all floats are integers effectively
                                if (current_df[col_name_excel].fillna(0) % 1 == 0).all():
                                    cell_fmt = int_format # Treat as integer
                                else: # General float format
                                    cell_fmt = workbook.add_format({'num_format': '0.00', 'border': 1, 'valign': 'top'})


                            ws.set_column(c_idx, c_idx, col_width, cell_fmt)
                        
                        if not current_df.empty:
                             ws.add_table(0, 0, len(current_df), len(current_df.columns) - 1, {
                                'name': f'Table_{re.sub(r"[^A-Za-z0-9_]", "", sheet_name_excel)}',
                                'style': 'TableStyleLight8',
                                'columns': [{'header': c} for c in current_df.columns]
                            })
                
                    # Define columns for each sheet
                    cols_00 = ['Date', 'Code projet', 'Nom', 'Grade', 'Heures', 'Libelle projet']
                    cols_01 = ['Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Rate DES', 'Total', 'Total DES']
                    cols_02 = ['Libelle projet', 'Total Heures', 'Total', 'Total DES', 'Estimees']
                    cols_03 = ['ID', 'Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Total', 
                               'coeff_total', 'priority_coeff', 'final_coeff', # Show the coefficients
                               'Adjusted Hours', 'Heures Retirées', 'Adjusted Cost']
                    # Result columns are dynamic, so pass None for selected_cols_excel

                    write_excel_sheet_final(base_df, '00_Base', cols_00)
                    write_excel_sheet_final(employee_summary_df, '01_Employee_Summary', cols_01)
                    write_excel_sheet_final(global_summary_df, '02_Global_Summary', cols_02)
                    write_excel_sheet_final(adjusted_df, '03_Adjusted', cols_03) 
                    write_excel_sheet_final(result_df, '04_Result', None) 

                output.seek(0)
                filename = f"Facturation_SLR_{parsed_mois_nom}_{annee}.xlsx"
                processing_logs.append(f"SUCCESS: Excel file generated and ready for download as '{filename}'.")
                messages.success(request, f"Report '{filename}' generated successfully!")
                response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response

            except pd.errors.EmptyDataError as ede:
                error_msg = f"ERROR: Pandas EmptyDataError - No data found in one of the Excel sheets or files. Details: {str(ede)}"
                processing_logs.append(f"{error_msg}<br><pre>{traceback.format_exc()}</pre>")
                messages.error(request, "An error occurred: Empty data encountered in one of the input files.")
            except KeyError as ke:
                error_msg = f"ERROR: KeyError - A required column or sheet name was not found. Details: {str(ke)}"
                processing_logs.append(f"{error_msg}<br><pre>{traceback.format_exc()}</pre>")
                messages.error(request, f"An error occurred: Missing column or sheet: {str(ke)}.")
            except ValueError as ve:
                error_msg = f"ERROR: ValueError - Issue with data types or values. Details: {str(ve)}"
                processing_logs.append(f"{error_msg}<br><pre>{traceback.format_exc()}</pre>")
                messages.error(request, f"An error occurred: Data value error: {str(ve)}.")
            except Exception as e:
                error_msg = f"ERROR: An unexpected error occurred during processing: {str(e)}"
                processing_logs.append(f"{error_msg}<br><pre>{traceback.format_exc()}</pre>")
                messages.error(request, "An error occurred while generating the report. See logs for details.")
        else: # Form is not valid
            processing_logs.append("ERROR: Form validation failed. Please check the uploaded files and try again.")
            for field, errors_list in form.errors.items():
                for error_item in errors_list:
                    processing_logs.append(f"ERROR (Form field: {field}): {error_item}")
            messages.error(request, "Form validation failed. Please correct the errors and try again.")


    context = {
        'form': form,
        'page_title': 'Facturation SLR',
        'processing_logs': processing_logs
    }
    return render(request, 'billing/facturation_slr.html', context)

@login_required
def mission_bulk_delete(request):
    if request.method == 'POST':
        try:
            selected_missions_ids = request.POST.getlist('selected_missions')
            # processing_logs.append(f"DEBUG: Received POST request for bulk delete. Selected missions IDs: {selected_missions_ids}") # processing_logs not defined here
            
            if not selected_missions_ids:
                # processing_logs.append("DEBUG: No missions selected for deletion")
                messages.warning(request, 'No missions were selected for deletion.')
                return redirect('mission_list')
            
            try:
                selected_missions_ids = [int(id_str) for id_str in selected_missions_ids]
            except ValueError:
                messages.error(request, 'Invalid mission ID format received.')
                return redirect('mission_list')

            existing_missions = Mission.objects.filter(id__in=selected_missions_ids)
            count_to_delete = existing_missions.count()
            # processing_logs.append(f"DEBUG: Found {count_to_delete} existing missions to delete")
            
            if count_to_delete > 0:
                existing_missions.delete()
                # processing_logs.append(f"DEBUG: Successfully deleted {count_to_delete} missions")
                messages.success(request, f'Successfully deleted {count_to_delete} mission(s).')
            else:
                # processing_logs.append("DEBUG: No existing missions found matching the selected IDs to delete")
                messages.warning(request, 'No valid missions were found to delete.')
        except Exception as e:
            # processing_logs.append(f"ERROR: Exception during bulk delete: {str(e)}")
            messages.error(request, f'An error occurred while deleting missions: {str(e)}')
    else:
        # processing_logs.append("DEBUG: Non-POST request received for bulk delete")
        messages.warning(request, 'Invalid request method.')
    
    return redirect('mission_list')
