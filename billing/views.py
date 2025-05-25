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
                db_resources_df['Grade'] = db_resources_df['grade'] # Assuming 'grade' field from model is what's needed
                db_resources_df['Rate'] = pd.to_numeric(db_resources_df['rate_ibm'], errors='coerce').fillna(0)
                db_resources_df['Rate DES'] = pd.to_numeric(db_resources_df['rate_des'], errors='coerce').fillna(0)
                processing_logs.append(f"INFO: Resource data loaded. Sample:<div class='log-table-sample'>{db_resources_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Fetch Mission Data ---
                missions_qs = Mission.objects.all()
                db_missions_df = pd.DataFrame(list(missions_qs.values('otp_l2', 'belgian_name', 'libelle_de_projet'))) # belgian_name is 'Libellé de Projet', libelle_de_projet is 'Belgian Name'
                if db_missions_df.empty:
                    processing_logs.append("ERROR: No missions found in the database.")
                    messages.error(request, "Processing Error: No missions found in the database.")
                    return render(request, 'billing/facturation_slr.html', {'form': form, 'page_title': 'Facturation SLR', 'processing_logs': processing_logs})
                db_missions_df['Code projet'] = db_missions_df['otp_l2']
                # 'Libelle projet' for merging with base_df should come from the model's 'belgian_name' field
                db_missions_df['Libelle projet'] = db_missions_df['belgian_name'].fillna('') 
                # 'Belgian Name' for merging with MAFE 'Customer Name' should come from model's 'libelle_de_projet'
                db_missions_df['MAFE Customer Name Match'] = db_missions_df['libelle_de_projet'].fillna('') 
                processing_logs.append(f"INFO: Mission data loaded. Sample:<div class='log-table-sample'>{db_missions_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Read Heures IBM file (base_df) ---
                processing_logs.append(f"INFO: Attempting to read data from '{heures_ibm_file_obj.name}'...")
                base_df = pd.read_excel(heures_ibm_file_obj, sheet_name='base', usecols="E,H,I,M,N")
                base_df.columns = ['Code projet', 'Nom', 'Grade', 'Date', 'Heures'] # Grade from IBM file
                base_df['Nom'] = base_df['Nom'].astype(str).str.lower().str.strip()
                base_df['Heures'] = pd.to_numeric(base_df['Heures'], errors='coerce').fillna(0)
                # Merge with Mission for Libelle projet (using model's 'belgian_name' as 'Libelle projet')
                base_df = base_df.merge(db_missions_df[['Code projet', 'Libelle projet']], on='Code projet', how='left')
                base_df['Libelle projet'] = base_df['Libelle projet'].fillna(base_df['Code projet']) # Fallback to Code projet if no Libelle
                processing_logs.append(f"INFO: Heures IBM data processed and merged with missions. Sample:<div class='log-table-sample'>{base_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Create employee_summary_df ---
                employee_summary_df = (
                    base_df.groupby(['Libelle projet', 'Nom', 'Grade'], as_index=False) # Grade here is from IBM file
                    .agg({'Heures': 'sum'})
                    .rename(columns={'Heures': 'Total Heures'})
                )
                # Merge with Resource for rates and DB Grade (model's 'grade')
                employee_summary_df = employee_summary_df.merge(
                    db_resources_df[['Nom', 'Rate', 'Rate DES', 'Grade_DB']], # Use a distinct name for DB Grade
                    left_on='Nom', right_on='Nom', how='left', suffixes=('', '_Resource')
                ).rename(columns={'Grade_DB': 'Grade'}) # Now 'Grade' is from DB
                
                employee_summary_df['Rate'] = employee_summary_df['Rate'].fillna(0)
                employee_summary_df['Rate DES'] = employee_summary_df['Rate DES'].fillna(0)
                employee_summary_df['Total'] = employee_summary_df['Total Heures'] * employee_summary_df['Rate']
                employee_summary_df['Total DES'] = employee_summary_df['Total Heures'] * employee_summary_df['Rate DES']
                processing_logs.append(f"INFO: Employee summary created. Sample:<div class='log-table-sample'>{employee_summary_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Read MAFE Report file (df_mafe) ---
                processing_logs.append(f"INFO: Attempting to read data from '{mafe_file_obj.name}'...")
                mafe_raw_df = pd.read_excel(mafe_file_obj, sheet_name='(Tab A) FULLY COMMITTED', header=None)
                df_mafe = pd.DataFrame() # Initialize
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
                    messages.error(request, f"Processing Error: MAFE file '{mafe_file_obj.name}' format error.")
                    # df_mafe will remain empty

                # --- Process mafe_subset_df ---
                mafe_subset_df = pd.DataFrame(columns=["Country", "Customer Name", "Libelle projet", "Estimees"]) # Initialize
                if not df_mafe.empty:
                    forecast_col_cleaned = next((col for col in df_mafe.columns if mois in col and 'Forecasts' in col and annee[-2:] in col), None)
                    if forecast_col_cleaned:
                        mafe_subset_df = df_mafe[['Country', 'Customer Name', forecast_col_cleaned]].rename(columns={forecast_col_cleaned: 'Estimees'})
                        # Map MAFE 'Customer Name' to 'Libelle projet' using missions (model's 'libelle_de_projet' as 'MAFE Customer Name Match', model's 'belgian_name' as 'Libelle projet')
                        mafe_subset_df = mafe_subset_df.merge(
                            db_missions_df[['MAFE Customer Name Match', 'Libelle projet']],
                            left_on='Customer Name', right_on='MAFE Customer Name Match', how='left'
                        )
                        # If 'Libelle projet' (from mission mapping) is NaN, use MAFE's 'Customer Name'
                        mafe_subset_df['Libelle projet'] = mafe_subset_df['Libelle projet_y'].fillna(mafe_subset_df['Customer Name'])
                        mafe_subset_df = mafe_subset_df.drop(columns=['Libelle projet_x', 'Libelle projet_y', 'MAFE Customer Name Match'], errors='ignore')

                    else:
                        processing_logs.append(f"WARNING: Could not find forecast column for {mois} {annee} in MAFE file.")
                else:
                     processing_logs.append(f"WARNING: MAFE data is empty, cannot create MAFE subset.")
                processing_logs.append(f"INFO: MAFE subset processed. Sample:<div class='log-table-sample'>{mafe_subset_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- summary_by_proj_df ---
                summary_by_proj_df = (
                    employee_summary_df.groupby('Libelle projet', as_index=False)
                    .agg({'Total Heures': 'sum', 'Total': 'sum', 'Total DES': 'sum'})
                )
                processing_logs.append(f"DEBUG: summary_by_proj_df created with {len(summary_by_proj_df)} rows.")

                # --- global_summary_df ---
                global_summary_df = pd.merge(
                    mafe_subset_df[['Libelle projet', 'Estimees']].drop_duplicates(subset=['Libelle projet']), # Ensure unique Libelle projet before merge
                    summary_by_proj_df,
                    on='Libelle projet', how='left' # Use left merge to keep all MAFE projects
                )
                global_summary_df[['Total Heures', 'Total', 'Total DES']] = global_summary_df[['Total Heures', 'Total', 'Total DES']].fillna(0)
                global_summary_df['Estimees'] = pd.to_numeric(global_summary_df['Estimees'].astype(str).str.strip().replace(['', '-', 'nan', 'None'], '0', regex=False), errors='coerce').fillna(0)
                processing_logs.append(f"DEBUG: global_summary_df created with {len(global_summary_df)} rows.")

                # --- adjusted_df ---
                adjusted_df = pd.merge(
                    employee_summary_df,
                    global_summary_df[['Libelle projet', 'Estimees']], # Estimees are now per Libelle projet
                    on='Libelle projet', how='left'
                )
                adjusted_df['Estimees'] = adjusted_df['Estimees'].fillna(0) # Ensure Estimees are not NaN after merge

                adjusted_df['Total_Projet_Cout'] = adjusted_df.groupby('Libelle projet')['Total'].transform('sum')
                adjusted_df['total_rate_proj'] = adjusted_df.groupby('Libelle projet')['Rate'].transform('sum')
                
                # Initialize Adjusted Hours with Total Heures by default
                adjusted_df['Adjusted Hours'] = adjusted_df['Total Heures']
                
                # Columns for detailed coefficient calculation (optional for final output but useful for debug)
                adjusted_df['coeff_total_raw'] = np.nan
                adjusted_df['coeff_total_capped'] = np.nan
                adjusted_df['priority_coeff'] = np.nan
                adjusted_df['final_coeff'] = np.nan

                # Mask for rows where adjustment calculation is possible
                can_calculate_coeffs_mask = (adjusted_df['Total_Projet_Cout'] > 0) & (adjusted_df['total_rate_proj'] > 0)
                
                if can_calculate_coeffs_mask.any():
                    # Calculate raw coefficient total
                    adjusted_df.loc[can_calculate_coeffs_mask, 'coeff_total_raw'] = \
                        adjusted_df.loc[can_calculate_coeffs_mask, 'Estimees'] / adjusted_df.loc[can_calculate_coeffs_mask, 'Total_Projet_Cout']
                    
                    # Cap Coeff_total at 1.0
                    adjusted_df.loc[can_calculate_coeffs_mask, 'coeff_total_capped'] = \
                        adjusted_df.loc[can_calculate_coeffs_mask, 'coeff_total_raw'].apply(lambda x: min(x, 1.0) if pd.notnull(x) else x)
                    
                    # Calculate priority coefficient
                    adjusted_df.loc[can_calculate_coeffs_mask, 'priority_coeff'] = \
                        adjusted_df.loc[can_calculate_coeffs_mask, 'Rate'] / adjusted_df.loc[can_calculate_coeffs_mask, 'total_rate_proj']
                    
                    # Calculate final coefficient using the capped total coefficient
                    adjusted_df.loc[can_calculate_coeffs_mask, 'final_coeff'] = \
                        adjusted_df.loc[can_calculate_coeffs_mask, 'coeff_total_capped'] * adjusted_df.loc[can_calculate_coeffs_mask, 'priority_coeff']
                    
                    # Calculate Adjusted Hours for the masked rows
                    calculated_adjusted_hours = (adjusted_df.loc[can_calculate_coeffs_mask, 'Total Heures'] * \
                                                (1 - adjusted_df.loc[can_calculate_coeffs_mask, 'final_coeff'])).round()
                    adjusted_df.loc[can_calculate_coeffs_mask, 'Adjusted Hours'] = calculated_adjusted_hours
                
                # Ensure Adjusted Hours are not negative
                adjusted_df['Adjusted Hours'] = adjusted_df['Adjusted Hours'].apply(lambda x: max(x, 0.0) if pd.notnull(x) else 0.0)
                
                adjusted_df['Heures Retirées'] = adjusted_df['Total Heures'] - adjusted_df['Adjusted Hours']
                adjusted_df['Adjusted Cost'] = adjusted_df['Adjusted Hours'] * adjusted_df['Rate']
                adjusted_df['ID'] = adjusted_df['Nom'].astype(str) + ' - ' + adjusted_df['Libelle projet'].astype(str)
                
                cols_for_adjusted_log = ['Libelle projet', 'Nom', 'Total Heures', 'Estimees', 'Total_Projet_Cout', 
                                         'coeff_total_raw', 'coeff_total_capped', 'priority_coeff', 'final_coeff', 'Adjusted Hours']
                # Ensure all columns exist before trying to select them for logging
                existing_cols_for_log = [col for col in cols_for_adjusted_log if col in adjusted_df.columns]
                if can_calculate_coeffs_mask.any() and existing_cols_for_log:
                     processing_logs.append(f"DEBUG: adjusted_df sample with calculations (first row where calculable):<div class='log-table-sample'>{adjusted_df[can_calculate_coeffs_mask][existing_cols_for_log].head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")
                
                cols_adjusted_final = ['ID', 'Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Total', 
                                       'Adjusted Hours', 'Heures Retirées', 'Adjusted Cost', 
                                       'coeff_total_raw', 'coeff_total_capped', 'priority_coeff', 'final_coeff'] # Include new coeffs
                # Ensure all selected columns exist in adjusted_df
                final_adjusted_cols_to_select = [col for col in cols_adjusted_final if col in adjusted_df.columns]
                adjusted_df = adjusted_df[final_adjusted_cols_to_select]
                processing_logs.append(f"DEBUG: adjusted_df created with {len(adjusted_df)} rows.")


                # --- result_df ---
                result_df = (
                    adjusted_df.groupby('Libelle projet', as_index=False)
                    .agg({'Total Heures': 'sum', 'Adjusted Hours': 'sum', 'Adjusted Cost': 'sum'})
                    # Merge with global_summary_df to get 'Estimees' for the final result
                    .merge(global_summary_df[['Libelle projet', 'Estimees']].drop_duplicates(subset=['Libelle projet']), on='Libelle projet', how='left')
                )
                result_df['Estimees'] = result_df['Estimees'].fillna(0) # Ensure Estimees are not NaN
                result_df['Ecart'] = result_df['Estimees'] - result_df['Adjusted Cost']
                processing_logs.append(f"DEBUG: result_df created with {len(result_df)} rows.")

                # --- Rounding ---
                for df_to_round in [employee_summary_df, global_summary_df, adjusted_df, result_df]:
                    if df_to_round is not None and not df_to_round.empty:
                        for col in df_to_round.select_dtypes(include=np.number).columns:
                            df_to_round[col] = df_to_round[col].round(0)

                # --- Excel Output ---
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    workbook = writer.book
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D2E9', 'border': 1})
                    int_format = workbook.add_format({'num_format': '0', 'border': 1})
                    default_format = workbook.add_format({'border': 1})


                    def handle_nan_values(df_input, sheet_name_log):
                        df_copy = df_input.copy() # Work on a copy
                        initial_nan_count = df_copy.isna().sum().sum()
                        if initial_nan_count > 0:
                            processing_logs.append(f"DEBUG: Found {initial_nan_count} NaN values in {sheet_name_log} before fallback handling.")
                            for col_nan in df_copy.columns:
                                if pd.api.types.is_numeric_dtype(df_copy[col_nan]):
                                    df_copy[col_nan] = df_copy[col_nan].fillna(0)
                                else:
                                    df_copy[col_nan] = df_copy[col_nan].fillna("N/A")
                            final_nan_count = df_copy.isna().sum().sum()
                            processing_logs.append(f"INFO: Applied NaN fallbacks to DataFrame for sheet '{sheet_name_log}'. NaN count reduced from {initial_nan_count} to {final_nan_count}.")
                        return df_copy

                    def write_excel_sheet(df_to_write, sheet_name_excel, selected_cols_excel=None):
                        if df_to_write is None or df_to_write.empty:
                            processing_logs.append(f"WARNING: DataFrame for sheet '{sheet_name_excel}' is empty. Skipping sheet.")
                            # Optionally, write an empty sheet with a message
                            empty_df_message = pd.DataFrame([{'Message': f'No data available for {sheet_name_excel}'}])
                            empty_df_message.to_excel(writer, sheet_name=sheet_name_excel, index=False, startrow=1, header=False)
                            ws = writer.sheets[sheet_name_excel]
                            ws.write(0, 0, 'Message', header_format)
                            ws.set_column(0, 0, 50, default_format)
                            return

                        df_processed = handle_nan_values(df_to_write, sheet_name_excel)
                        
                        # Original filtering logic:
                        # if 'Total Heures' in df_processed.columns and sheet_name_excel != '03_Adjusted':
                        #     df_processed = df_processed[df_processed['Total Heures'] != 0].copy()
                        #     processing_logs.append(f"DEBUG: {sheet_name_excel} after filtering out zero 'Total Heures': {len(df_processed)} rows")
                        
                        if selected_cols_excel:
                            # Ensure all selected columns exist
                            existing_selected_cols = [col for col in selected_cols_excel if col in df_processed.columns]
                            if len(existing_selected_cols) != len(selected_cols_excel):
                                missing = set(selected_cols_excel) - set(existing_selected_cols)
                                processing_logs.append(f"WARNING: Missing columns {missing} for sheet {sheet_name_excel}. Using available columns.")
                            df_processed = df_processed[existing_selected_cols]
                        
                        if df_processed.empty and selected_cols_excel: # If filtering made it empty
                             processing_logs.append(f"WARNING: DataFrame for sheet '{sheet_name_excel}' became empty after column selection/filtering. Skipping content write.")
                             # Write a message instead
                             empty_df_message = pd.DataFrame([{'Message': f'No data after filtering for {sheet_name_excel}'}])
                             empty_df_message.to_excel(writer, sheet_name=sheet_name_excel, index=False, startrow=1, header=False)
                             ws = writer.sheets[sheet_name_excel]
                             ws.write(0, 0, 'Message', header_format)
                             ws.set_column(0, 0, 50, default_format)
                             return

                        df_processed.to_excel(writer, sheet_name=sheet_name_excel, index=False, startrow=1, header=False)
                        ws = writer.sheets[sheet_name_excel]
                        for i, col_name_excel in enumerate(df_processed.columns):
                            ws.write(0, i, col_name_excel, header_format)
                            # Determine column width
                            # Max of header length, max content length (sampled), or default 15
                            try:
                                max_len = max(
                                    len(str(col_name_excel)),
                                    df_processed[col_name_excel].astype(str).map(len).max() if not df_processed.empty else 0
                                )
                                width = max(15, max_len + 2)
                            except Exception: # Fallback if error during width calculation
                                width = max(15, len(str(col_name_excel)) + 2)
                            
                            cell_fmt = int_format if pd.api.types.is_integer_dtype(df_processed[col_name_excel]) and df_processed[col_name_excel].notna().any() else default_format
                            ws.set_column(i, i, width, cell_fmt)
                        
                        if not df_processed.empty:
                             ws.add_table(0, 0, len(df_processed), len(df_processed.columns) - 1, {
                                'name': f'Table_{sheet_name_excel.replace(" ", "_")}', # Ensure valid table name
                                'style': 'TableStyleLight8',
                                'columns': [{'header': c} for c in df_processed.columns]
                            })
                        else: # If df_processed became empty after all, write a message
                            ws.write(1,0, "No data available for this sheet after processing.", default_format)


                    # Write each sheet
                    write_excel_sheet(base_df, '00_Base', ['Date', 'Code projet', 'Nom', 'Grade', 'Heures', 'Libelle projet'])
                    write_excel_sheet(employee_summary_df, '01_Employee_Summary', ['Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Rate DES', 'Total', 'Total DES'])
                    write_excel_sheet(global_summary_df, '02_Global_Summary', ['Libelle projet', 'Total Heures', 'Total', 'Total DES', 'Estimees'])
                    # For adjusted_df, use the 'final_adjusted_cols_to_select' which includes the new coefficient columns
                    write_excel_sheet(adjusted_df, '03_Adjusted', final_adjusted_cols_to_select) 
                    write_excel_sheet(result_df, '04_Result') # result_df columns are dynamic based on its definition

                output.seek(0)
                filename = f"Facturation_SLR_{parsed_mois_nom}_{annee}.xlsx" # Use parsed_mois_nom for filename
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
        else:
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
            processing_logs.append(f"DEBUG: Received POST request for bulk delete. Selected missions IDs: {selected_missions_ids}")
            
            if not selected_missions_ids:
                processing_logs.append("DEBUG: No missions selected for deletion")
                messages.warning(request, 'No missions were selected for deletion.')
                return redirect('mission_list')
            
            # Ensure IDs are integers for querying
            try:
                selected_missions_ids = [int(id_str) for id_str in selected_missions_ids]
            except ValueError:
                messages.error(request, 'Invalid mission ID format received.')
                return redirect('mission_list')

            existing_missions = Mission.objects.filter(id__in=selected_missions_ids)
            count_to_delete = existing_missions.count()
            processing_logs.append(f"DEBUG: Found {count_to_delete} existing missions to delete")
            
            if count_to_delete > 0:
                existing_missions.delete()
                processing_logs.append(f"DEBUG: Successfully deleted {count_to_delete} missions")
                messages.success(request, f'Successfully deleted {count_to_delete} mission(s).')
            else:
                processing_logs.append("DEBUG: No existing missions found matching the selected IDs to delete")
                messages.warning(request, 'No valid missions were found to delete.')
        except Exception as e:
            processing_logs.append(f"ERROR: Exception during bulk delete: {str(e)}")
            messages.error(request, f'An error occurred while deleting missions: {str(e)}')
    else:
        processing_logs.append("DEBUG: Non-POST request received for bulk delete")
        messages.warning(request, 'Invalid request method.')
    
    return redirect('mission_list')
