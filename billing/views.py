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
                db_resources_df = pd.DataFrame(list(resources_qs.values('full_name', 'grade', 'grade_des', 'rate_ibm', 'rate_des')))
                if db_resources_df.empty:
                    processing_logs.append("ERROR: No resources found in the database.")
                    return render(request, 'billing/facturation_slr.html', {'form': form, 'page_title': 'Facturation SLR', 'processing_logs': processing_logs})
                db_resources_df['Resource Name'] = db_resources_df['full_name'].astype(str).str.lower().str.strip()
                db_resources_df['Resource Grade'] = db_resources_df['grade']
                db_resources_df['Rate IBM (Resource)'] = pd.to_numeric(db_resources_df['rate_ibm'], errors='coerce').fillna(0)
                db_resources_df['Rate DES (Resource)'] = pd.to_numeric(db_resources_df['rate_des'], errors='coerce').fillna(0)
                processing_logs.append(f"INFO: Resource data loaded. Sample:<div class='log-table-sample'>{db_resources_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Fetch Mission Data ---
                missions_qs = Mission.objects.all()
                db_missions_df = pd.DataFrame(list(missions_qs.values('otp_l2', 'belgian_name', 'libelle_de_projet', 'code_type')))
                if db_missions_df.empty:
                    processing_logs.append("ERROR: No missions found in the database.")
                    return render(request, 'billing/facturation_slr.html', {'form': form, 'page_title': 'Facturation SLR', 'processing_logs': processing_logs})
                db_missions_df['Code projet DB'] = db_missions_df['otp_l2']
                db_missions_df['Libelle Projet DB'] = db_missions_df['belgian_name'].fillna('')
                db_missions_df['Belgian Name DB'] = db_missions_df['libelle_de_projet']
                processing_logs.append(f"INFO: Mission data loaded. Sample:<div class='log-table-sample'>{db_missions_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Read Heures IBM file (base_df) ---
                processing_logs.append(f"INFO: Attempting to read data from '{heures_ibm_file_obj.name}'...")
                base_df = pd.read_excel(heures_ibm_file_obj, sheet_name='base', usecols="E,H,I,M,N")
                base_df.columns = ['Code projet', 'Nom', 'Grade from File', 'Date', 'Heures']
                base_df['Nom'] = base_df['Nom'].astype(str).str.lower().str.strip()
                base_df['Heures'] = pd.to_numeric(base_df['Heures'], errors='coerce').fillna(0)
                # Merge with Mission for Libelle projet
                base_df = base_df.merge(db_missions_df[['Code projet DB', 'Libelle Projet DB']], left_on='Code projet', right_on='Code projet DB', how='left')
                base_df['Libelle projet'] = base_df['Libelle Projet DB'].fillna('')
                processing_logs.append(f"INFO: Heures IBM data processed and merged with missions. Sample:<div class='log-table-sample'>{base_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Create employee_summary_df ---
                employee_summary_df = (
                    base_df.groupby(['Libelle projet', 'Nom', 'Grade from File'], as_index=False)
                    .agg({'Heures': 'sum'})
                    .rename(columns={'Heures': 'Total Heures'})
                )
                # Merge with Resource for rates
                employee_summary_df = employee_summary_df.merge(
                    db_resources_df[['Resource Name', 'Resource Grade', 'Rate IBM (Resource)', 'Rate DES (Resource)']],
                    left_on='Nom', right_on='Resource Name', how='left'
                )
                employee_summary_df['Rate'] = employee_summary_df['Rate IBM (Resource)'].fillna(0)
                employee_summary_df['Rate DES'] = employee_summary_df['Rate DES (Resource)'].fillna(0)
                employee_summary_df['Total'] = employee_summary_df['Total Heures'] * employee_summary_df['Rate']
                employee_summary_df['Total DES'] = employee_summary_df['Total Heures'] * employee_summary_df['Rate DES']

                # Initial filtering of employee_summary_df
                processing_logs.append(f"DEBUG: employee_summary_df before 'Total Heures != 0' filter: {len(employee_summary_df)} rows.")
                if 'Total Heures' in employee_summary_df.columns:
                    employee_summary_df = employee_summary_df[employee_summary_df['Total Heures'] != 0].copy()
                    processing_logs.append(f"DEBUG: employee_summary_df after 'Total Heures != 0' filter: {len(employee_summary_df)} rows.")
                else:
                    processing_logs.append("WARNING: 'Total Heures' column not found in employee_summary_df for critical early filtering.")

                processing_logs.append(f"INFO: Employee summary created. Sample:<div class='log-table-sample'>{employee_summary_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- Read MAFE Report file (df_mafe) ---
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

                # --- Process mafe_subset_df ---
                forecast_col_cleaned = next((col for col in df_mafe.columns if mois in col and 'Forecasts' in col and annee[-2:] in col), None)
                if forecast_col_cleaned:
                    mafe_subset_df = df_mafe[['Country', 'Customer Name', forecast_col_cleaned]].rename(columns={forecast_col_cleaned: 'Estimees'})
                    # Map Customer Name to Libelle projet using missions
                    mafe_subset_df = mafe_subset_df.merge(
                        db_missions_df[['Belgian Name DB', 'Libelle Projet DB']],
                        left_on='Customer Name', right_on='Belgian Name DB', how='left'
                    )
                    mafe_subset_df['Libelle projet'] = mafe_subset_df['Libelle Projet DB']
                    mafe_subset_df['Libelle projet'] = mafe_subset_df['Libelle projet'].fillna(mafe_subset_df['Customer Name'])
                else:
                    mafe_subset_df = pd.DataFrame(columns=["Country", "Customer Name", "Libelle projet", "Estimees"])
                processing_logs.append(f"INFO: MAFE subset processed. Sample:<div class='log-table-sample'>{mafe_subset_df.head(1).to_html(classes='table table-sm table-bordered table-striped my-2 log-table-sample-width', index=False, border=0)}</div>")

                # --- summary_by_proj_df ---
                summary_by_proj_df = (
                    employee_summary_df.groupby('Libelle projet', as_index=False)
                    .agg({'Total Heures': 'sum', 'Total': 'sum', 'Total DES': 'sum'})
                )
                processing_logs.append(f"DEBUG: summary_by_proj_df created with {len(summary_by_proj_df)} rows.")

                # --- global_summary_df ---
                global_summary_df = pd.merge(
                    mafe_subset_df[['Libelle projet', 'Estimees']].drop_duplicates(),
                    summary_by_proj_df,
                    on='Libelle projet', how='left'
                )
                global_summary_df[['Total Heures', 'Total', 'Total DES']] = global_summary_df[['Total Heures', 'Total', 'Total DES']].fillna(0)
                global_summary_df['Estimees'] = pd.to_numeric(global_summary_df['Estimees'].astype(str).str.strip().replace(['', '-', 'nan', 'None'], '0'), errors='coerce').fillna(0)
                processing_logs.append(f"DEBUG: global_summary_df created with {len(global_summary_df)} rows.")

                # Update Mission records with calculation results
                processing_logs.append("INFO: Attempting to update Mission records with calculated 'Total Heures' and 'Estimée'...")
                if not global_summary_df.empty:
                    updated_missions_count = 0
                    period_for_calculation = f"{parsed_mois_nom} {parsed_annee_full}"

                    for index, row in global_summary_df.iterrows():
                        mission_label = row.get('Libelle projet')
                        total_heures_calc = row.get('Total Heures')
                        estimee_calc = row.get('Estimees')

                        if mission_label is not None:
                            try:
                                mission_obj = Mission.objects.filter(belgian_name=mission_label).first()
                                if mission_obj:
                                    mission_obj.calculated_total_heures = total_heures_calc if pd.notna(total_heures_calc) else None
                                    mission_obj.calculated_estimee = estimee_calc if pd.notna(estimee_calc) else None
                                    mission_obj.calculation_period = period_for_calculation
                                    mission_obj.save(update_fields=['calculated_total_heures', 'calculated_estimee', 'calculation_period'])
                                    updated_missions_count += 1
                                else:
                                    processing_logs.append(f"WARNING: Mission with Libelle projet '{mission_label}' not found in DB for updating calculation results.")
                            except Exception as e_update:
                                processing_logs.append(f"ERROR: Could not update mission '{mission_label}' with calculation results: {str(e_update)}")
                    processing_logs.append(f"INFO: Updated {updated_missions_count} Mission records with calculation results for period {period_for_calculation}.")
                else:
                    processing_logs.append("WARNING: global_summary_df is empty. Skipping update of Mission calculation fields.")

                # --- adjusted_df ---
                adjusted_df = pd.merge(
                    employee_summary_df,
                    global_summary_df[['Libelle projet', 'Estimees']],
                    on='Libelle projet', how='left'
                )
                adjusted_df['Total_Projet_Cout'] = adjusted_df.groupby('Libelle projet')['Total'].transform('sum')
                adjusted_df['total_rate_proj'] = adjusted_df.groupby('Libelle projet')['Rate'].transform('sum')
                adjusted_df = adjusted_df[(adjusted_df['Total_Projet_Cout'] > 0) & (adjusted_df['total_rate_proj'] > 0)]
                adjusted_df['coeff_total'] = adjusted_df['Estimees'] / adjusted_df['Total_Projet_Cout']
                adjusted_df['priority_coeff'] = adjusted_df['Rate'] / adjusted_df['total_rate_proj']
                adjusted_df['final_coeff'] = adjusted_df['coeff_total'] * adjusted_df['priority_coeff']
                adjusted_df['Adjusted Hours'] = (adjusted_df['Total Heures'] * (1 - adjusted_df['final_coeff'])).round()
                adjusted_df['Adjusted Hours'] = adjusted_df['Adjusted Hours'].apply(lambda x: max(x, 0))
                adjusted_df['Heures Retirées'] = adjusted_df['Total Heures'] - adjusted_df['Adjusted Hours']
                adjusted_df['Adjusted Cost'] = adjusted_df['Adjusted Hours'] * adjusted_df['Rate']
                adjusted_df['ID'] = adjusted_df['Nom'].astype(str) + ' - ' + adjusted_df['Libelle projet'].astype(str)
                cols = ['ID'] + [col for col in adjusted_df.columns if col != 'ID']
                adjusted_df = adjusted_df[cols]
                processing_logs.append(f"DEBUG: adjusted_df created with {len(adjusted_df)} rows.")

                # --- result_df ---
                result_df = (
                    adjusted_df.groupby('Libelle projet', as_index=False)
                    .agg({'Total Heures': 'sum', 'Adjusted Hours': 'sum', 'Adjusted Cost': 'sum'})
                    .merge(global_summary_df[['Libelle projet', 'Estimees']], on='Libelle projet', how='left')
                )
                result_df['Ecart'] = result_df['Estimees'] - result_df['Adjusted Cost']
                processing_logs.append(f"DEBUG: result_df created with {len(result_df)} rows.")

                # --- Rounding ---
                for df in [employee_summary_df, global_summary_df, adjusted_df, result_df]:
                    for col in df.select_dtypes(include='number').columns:
                        df[col] = df[col].round(0)

                # --- Excel Output ---
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    workbook = writer.book
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D2E9'})
                    int_format = workbook.add_format({'num_format': '0'})

                    def handle_nan_values(df, sheet_name):
                        """Handle NaN values in DataFrame before writing to Excel."""
                        initial_nan_count = df.isna().sum().sum()
                        if initial_nan_count > 0:
                            processing_logs.append(f"DEBUG: Found {initial_nan_count} NaN values in {sheet_name} before fallback handling.")
                            
                            for col in df.columns:
                                if pd.api.types.is_numeric_dtype(df[col]):
                                    df[col] = df[col].fillna(0)
                                else:
                                    df[col] = df[col].fillna("N/A")
                            
                            final_nan_count = df.isna().sum().sum()
                            processing_logs.append(f"INFO: Applied NaN fallbacks (0 for numeric, 'N/A' for string) to DataFrame for sheet '{sheet_name}'. NaN count reduced from {initial_nan_count} to {final_nan_count}.")
                        return df

                    def write(df, sheet, selected_cols=None):
                        # Handle NaN values before any other processing
                        df = handle_nan_values(df, sheet)
                        
                        # Final filtering check before writing to Excel
                        if 'Total Heures' in df.columns:
                            processing_logs.append(f"DEBUG: {sheet} before final filter: {len(df)} rows")
                            df = df[df['Total Heures'] != 0].copy()
                            processing_logs.append(f"DEBUG: {sheet} after final filter: {len(df)} rows")
                        
                        if selected_cols:
                            df = df[selected_cols]
                        df.to_excel(writer, sheet_name=sheet, index=False, startrow=1, header=False)
                        ws = writer.sheets[sheet]
                        for i, col in enumerate(df.columns):
                            ws.write(0, i, col, header_format)
                            width = max(15, len(str(col)) + 2)
                            ws.set_column(i, i, width, int_format if pd.api.types.is_integer_dtype(df[col]) else None)
                        ws.add_table(0, 0, len(df), len(df.columns) - 1, {
                            'name': f'Table_{sheet}',
                            'style': 'TableStyleLight8',
                            'columns': [{'header': c} for c in df.columns]
                        })

                    # Write each sheet with NaN handling and final filtering
                    write(base_df[['Date', 'Code projet', 'Nom', 'Grade from File', 'Heures', 'Libelle projet']], '00_Base')
                    write(employee_summary_df[['Libelle projet', 'Nom', 'Grade from File', 'Total Heures', 'Rate', 'Rate DES', 'Total', 'Total DES']], '01_Employee_Summary')
                    write(global_summary_df[['Libelle projet', 'Total Heures', 'Total', 'Total DES', 'Estimees']], '02_Global_Summary')
                    write(adjusted_df[['ID', 'Libelle projet', 'Nom', 'Grade from File', 'Total Heures', 'Rate', 'Total', 'Adjusted Hours', 'Heures Retirées', 'Adjusted Cost']], '03_Adjusted')
                    write(result_df, '04_Result')

                output.seek(0)
                filename = f"Facturation_SLR_{mois}_{annee}.xlsx"
                processing_logs.append(f"SUCCESS: Excel file generated and ready for download as '{filename}'.")
                response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
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
