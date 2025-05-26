from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Resource, Mission
from .forms import ResourceForm, MissionForm, SLRFileUploadForm
import pandas as pd
import numpy as np
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
import uuid
from pathlib import Path
from django.conf import settings

# Define temporary storage path for SLR runs
TEMP_FILES_BASE_DIR = Path(settings.MEDIA_ROOT) / 'slr_temp_runs'
TEMP_FILES_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Create your views here.

@login_required
def home(request):
    import json
    from pathlib import Path
    from django.conf import settings
    import pandas as pd

    last_slr_run_id = request.session.get('last_slr_run_id')
    print(f"DEBUG: Retrieved last_slr_run_id from session: {last_slr_run_id}")
    data_available = False
    libelle_projets_list = []
    overall_kpis = {}
    projects_data_for_js = {}

    if last_slr_run_id:
        run_dir = Path(settings.MEDIA_ROOT) / 'slr_temp_runs' / last_slr_run_id
        print(f"DEBUG: Constructed run_dir: {run_dir}")
        # Check for each required parquet file
        parquet_files = ['result_initial.parquet', 'employee_summary_initial.parquet', 'global_summary_initial.parquet']
        parquet_exists = {}
        for fname in parquet_files:
            fpath = run_dir / fname
            exists = fpath.exists()
            parquet_exists[fname] = exists
            print(f"DEBUG: Checking for Parquet file: {fpath}, Exists: {exists}")
        try:
            result_df = pd.read_parquet(run_dir / 'result_initial.parquet')
            print(f"DEBUG: Loaded result_df, shape: {result_df.shape}")
            employee_summary_df = pd.read_parquet(run_dir / 'employee_summary_initial.parquet')
            print(f"DEBUG: Loaded employee_summary_df, shape: {employee_summary_df.shape}")
            global_summary_df = pd.read_parquet(run_dir / 'global_summary_initial.parquet')
            print(f"DEBUG: Loaded global_summary_df, shape: {global_summary_df.shape}")
            data_available = True
        except Exception as e:
            print(f"ERROR: Failed to load one or more Parquet files: {e}")
            data_available = False

    if data_available:
        # Prepare project list
        libelle_projets_list = sorted(result_df['Libelle projet'].dropna().unique())
        print(f"DEBUG: libelle_projets_list: {libelle_projets_list}")
        # Overall KPIs
        nb_employes = employee_summary_df['Nom'].nunique()
        total_budget_estime = result_df['Estimees'].sum()
        total_adjusted_cost = result_df['Adjusted Cost'].sum()
        total_ecart = result_df['Ecart'].sum()
        pct_ajustement = ((total_budget_estime - total_adjusted_cost) / total_budget_estime * 100) if total_budget_estime else 0
        overall_kpis = {
            'nb_employes': int(nb_employes),
            'total_budget_estime': float(total_budget_estime),
            'total_adjusted_cost': float(total_adjusted_cost),
            'total_ecart': float(total_ecart),
            'pct_ajustement': float(pct_ajustement)
        }
        print(f"DEBUG: overall_kpis: {overall_kpis}")
        # Prepare per-project data
        for libelle in libelle_projets_list:
            proj_result = result_df[result_df['Libelle projet'] == libelle]
            proj_employees = employee_summary_df[employee_summary_df['Libelle projet'] == libelle]
            nb_employes_proj = proj_employees['Nom'].nunique()
            budget_estime = proj_result['Estimees'].sum()
            adjusted_cost = proj_result['Adjusted Cost'].sum()
            ecart = proj_result['Ecart'].sum()
            pct_ajustement = ((budget_estime - adjusted_cost) / budget_estime * 100) if budget_estime else 0
            projects_data_for_js[libelle] = {
                'nbEmployes': int(nb_employes_proj),
                'budgetEstime': float(budget_estime),
                'adjustedCost': float(adjusted_cost),
                'ecart': float(ecart),
                'pctAjustement': float(pct_ajustement)
            }
        print(f"DEBUG: projects_data_for_js type: {type(projects_data_for_js)}, Number of projects: {len(projects_data_for_js) if isinstance(projects_data_for_js, dict) else 'N/A'}")
    context = {
        'data_available': data_available,
        'libelle_projets_list': libelle_projets_list,
        'overall_kpis': overall_kpis,
        'projects_data_json_from_view': json.dumps(projects_data_for_js),
    }
    print(f"DEBUG: Context for home.html: data_available={context.get('data_available')}")
    print(f"DEBUG: Context projects_data_json: {context.get('projects_data_json_from_view')[:200]}...")
    return render(request, 'billing/home.html', context)

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
        processing_logs.append(f"DEBUG: POST request received. POST data: {request.POST}")
        
        form = SLRFileUploadForm(request.POST, request.FILES)
        
        # Debug: log all files in request.FILES
        processing_logs.append('FILES received: ' + ', '.join(f'{k}: {v.name}' for k, v in request.FILES.items()))

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
                'processing_logs': processing_logs,
                'page_title': 'Facturation SLR',
            }
            return render(request, 'billing/facturation_slr.html', context)

        try:
            # Generate a unique run ID
            run_id = str(uuid.uuid4())
            run_dir = TEMP_FILES_BASE_DIR / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            processing_logs.append(f"DEBUG: Created temporary directory for run_id {run_id} at {run_dir}")

            # Process Heures IBM file
            heures_ibm_file_obj.seek(0)
            base_df = pd.read_excel(heures_ibm_file_obj, sheet_name='base', usecols="E,H,I,M,N")
            base_df.columns = ['Code projet', 'Nom', 'Grade', 'Date', 'Heures']
            processing_logs.append(f"INFO: Heures IBM file parsed. base_df shape: {base_df.shape}")

            # Process MAFE report file
            mafe_file_obj.seek(0)
            mafe_raw = pd.read_excel(mafe_file_obj, sheet_name='(Tab A) FULLY COMMITTED', header=None)
            mafe_raw.columns = mafe_raw.iloc[14].astype(str).str.strip().str.replace('\n', ' ').str.replace('\r', ' ')
            mafe_df = mafe_raw.drop(index=list(range(0, 15))).reset_index(drop=True)
            processing_logs.append(f"INFO: MAFE report file parsed. mafe_df shape: {mafe_df.shape}")

            # --- MATCH main.py LOGIC ---
            processing_logs.append("DEBUG: Starting calculations...")
            
            # 1. Prepare base_df (Heures IBM) - already loaded
            # 2. Prepare codes_df from Mission model
            codes_qs = Mission.objects.all().values('otp_l2', 'libelle_de_projet')
            codes_df = pd.DataFrame(list(codes_qs))
            codes_df = codes_df.rename(columns={'otp_l2': 'Code projet', 'libelle_de_projet': 'Libelle projet'})
            codes_df['Libelle projet'] = codes_df['Libelle projet'].fillna('Code France')
            base_df = base_df.merge(codes_df[['Code projet', 'Libelle projet']], on='Code projet', how='left')
            processing_logs.append("DEBUG: Codes merged with base_df")

            # 3. Prepare consultants_df from Resource model
            consultants_qs = Resource.objects.all().values('full_name', 'rate_ibm', 'rate_des', 'grade')
            consultants_df = pd.DataFrame(list(consultants_qs))
            consultants_df = consultants_df.rename(columns={'full_name': 'Nom', 'rate_ibm': 'Rate', 'rate_des': 'Rate DES', 'grade': 'Grade'})
            base_df['Nom'] = base_df['Nom'].astype(str).str.lower().str.strip()
            consultants_df['Nom'] = consultants_df['Nom'].astype(str).str.lower().str.strip()
            base_df['Heures'] = pd.to_numeric(base_df['Heures'], errors='coerce').fillna(0)
            consultants_df['Rate'] = pd.to_numeric(consultants_df['Rate'], errors='coerce').fillna(0)
            consultants_df['Rate DES'] = pd.to_numeric(consultants_df['Rate DES'], errors='coerce').fillna(0)
            processing_logs.append("DEBUG: Consultants data prepared")

            # 4. Prepare MAFE file - match main.py logic
            mois_mapping = {
                'Janvier': 'Jan', 'Février': 'Feb', 'Mars': 'Mar', 'Avril': 'Apr', 'Mai': 'May', 'Juin': 'Jun',
                'Juillet': 'Jul', 'Août': 'Aug', 'Septembre': 'Sep', 'Octobre': 'Oct', 'Novembre': 'Nov', 'Décembre': 'Dec',
                'Jan': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Apr', 'May': 'May', 'Jun': 'Jun',
                'Jul': 'Jul', 'Aug': 'Aug', 'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dec'
            }
            match = re.search(r'(Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\d]*(\d{2,4})', heures_ibm_file_obj.name)
            mois = mois_mapping.get(match.group(1), match.group(1)) if match else ''
            annee = match.group(2) if match else ''
            processing_logs.append(f"DEBUG: Month and year extracted: {mois} {annee}")

            # Find forecast column in MAFE
            forecast_col_cleaned = next((col for col in mafe_df.columns if mois in col and 'Forecasts' in col and annee[-2:] in col), None)
            if forecast_col_cleaned:
                mafe_subset = mafe_df[['Country', 'Customer Name', forecast_col_cleaned]].rename(columns={forecast_col_cleaned: 'Estimees'})
                # Get Belgian Name mapping from Mission model
                belgian_names = Mission.objects.values('belgian_name', 'libelle_de_projet')
                belgian_names_df = pd.DataFrame(list(belgian_names))
                if not belgian_names_df.empty:
                    belgian_names_df = belgian_names_df.rename(columns={'belgian_name': 'Customer Name', 'libelle_de_projet': 'Libelle projet'})
                    mafe_subset = mafe_subset.merge(belgian_names_df, on='Customer Name', how='left')
                mafe_subset['Libelle projet'] = mafe_subset['Libelle projet'].fillna(mafe_subset['Customer Name'])
            else:
                mafe_subset = pd.DataFrame(columns=["Country", "Customer Name", "Libelle projet", "Estimees"])
            processing_logs.append("DEBUG: MAFE data prepared with forecast column")

            # 6. Employee summary
            processing_logs.append("DEBUG: Starting employee summary calculations")
            employee_summary = (
                base_df.groupby(['Libelle projet', 'Nom', 'Grade'], as_index=False)
                .agg({'Heures': 'sum'})
                .rename(columns={'Heures': 'Total Heures'})
                .merge(consultants_df[['Nom', 'Rate']], on='Nom', how='left')
                .merge(consultants_df[['Nom', 'Rate DES']], on='Nom', how='left')
            )
            employee_summary['Total'] = employee_summary['Rate'] * employee_summary['Total Heures']
            employee_summary['Total DES'] = employee_summary['Rate DES'] * employee_summary['Total Heures']
            processing_logs.append("DEBUG: Employee summary calculated")

            summary_by_proj = employee_summary.groupby('Libelle projet', as_index=False).agg({'Total Heures': 'sum', 'Total': 'sum', 'Total DES': 'sum'})
            global_summary = pd.merge(mafe_subset[['Libelle projet', 'Estimees']].drop_duplicates(), summary_by_proj, on='Libelle projet', how='left')
            global_summary[['Total Heures', 'Total', 'Total DES']] = global_summary[['Total Heures', 'Total', 'Total DES']].fillna(0)
            global_summary['Estimees'] = pd.to_numeric(global_summary['Estimees'].astype(str).str.strip().replace(['', '-', 'nan', 'None'], '0'), errors='coerce').fillna(0)
            processing_logs.append("DEBUG: Global summary calculated")

            adjusted = employee_summary.merge(global_summary[['Libelle projet', 'Estimees']], on='Libelle projet', how='left')
            adjusted['Total_Projet_Cout'] = adjusted.groupby('Libelle projet')['Total'].transform('sum')
            
            # Robust calculation of coeff_total using np.where to handle zero denominators
            adjusted['coeff_total'] = np.where(
                adjusted['Total_Projet_Cout'] > 0,
                adjusted['Estimees'] / adjusted['Total_Projet_Cout'],
                0
            )
            
            adjusted['total_rate_proj'] = adjusted.groupby('Libelle projet')['Rate'].transform('sum')
            
            # Robust calculation of priority_coeff using np.where to handle zero denominators
            adjusted['priority_coeff'] = np.where(
                adjusted['total_rate_proj'] > 0,
                adjusted['Rate'] / adjusted['total_rate_proj'],
                0
            )
            
            # Calculate final_coeff after ensuring both intermediate coefficients are robust
            adjusted['final_coeff'] = adjusted['coeff_total'] * adjusted['priority_coeff']
            
            # Initial Adjusted Hours calculation
            adjusted['Adjusted Hours'] = (adjusted['Total Heures'] * (1 - adjusted['final_coeff'])).round()
            adjusted['Adjusted Hours'] = adjusted['Adjusted Hours'].apply(lambda x: max(x, 0))
            
            # Apply 30% rule for cases where Adjusted Hours is 0 but Total Heures > 0
            condition_for_30_pct_rule = (adjusted['Adjusted Hours'] == 0) & (adjusted['Total Heures'] > 0)
            adjusted.loc[condition_for_30_pct_rule, 'Adjusted Hours'] = \
                (adjusted.loc[condition_for_30_pct_rule, 'Total Heures'] * 0.3).round()
            
            # Ensure Adjusted Hours remains non-negative (extra safeguard)
            adjusted['Adjusted Hours'] = adjusted['Adjusted Hours'].apply(lambda x: max(x, 0))
            
            # Calculate Heures Retirées and Adjusted Cost using the final Adjusted Hours
            adjusted['Heures Retirées'] = adjusted['Total Heures'] - adjusted['Adjusted Hours']
            adjusted['Adjusted Cost'] = adjusted['Adjusted Hours'] * adjusted['Rate']
            adjusted['ID'] = adjusted['Nom'].astype(str) + ' - ' + adjusted['Libelle projet'].astype(str)
            processing_logs.append("DEBUG: Adjusted calculations completed with robust coefficient handling and 30% rule applied")

            cols = ['ID'] + [col for col in adjusted.columns if col != 'ID']
            adjusted = adjusted[cols]

            result = (
                adjusted
                .groupby('Libelle projet', as_index=False)
                .agg({'Total Heures': 'sum', 'Adjusted Hours': 'sum', 'Adjusted Cost': 'sum', 'Heures Retirées': 'sum'})
                .merge(global_summary[['Libelle projet', 'Estimees']], on='Libelle projet', how='left')
            )
            result['Ecart'] = result['Estimees'] - result['Adjusted Cost']
            processing_logs.append("DEBUG: Final result calculations completed")

            for df in [employee_summary, global_summary, adjusted, result]:
                for col in df.select_dtypes(include='number').columns:
                    df[col] = df[col].round(0)

            # Save all key DataFrames to Parquet files
            try:
                base_df.to_parquet(run_dir / 'base_df.parquet')
                consultants_df.to_parquet(run_dir / 'consultants_df.parquet')
                mafe_df.to_parquet(run_dir / 'mafe_df.parquet')
                codes_df.to_parquet(run_dir / 'codes_df.parquet')
                employee_summary.to_parquet(run_dir / 'employee_summary_initial.parquet')
                global_summary.to_parquet(run_dir / 'global_summary_initial.parquet')
                adjusted.to_parquet(run_dir / 'adjusted_initial.parquet')
                result.to_parquet(run_dir / 'result_initial.parquet')
                processing_logs.append(f"INFO: All DataFrames for run_id {run_id} saved to Parquet files.")
            except Exception as e:
                processing_logs.append(f"ERROR: Failed to save DataFrames for run_id {run_id}: {str(e)}")
                raise

            # Generate Excel file
            processing_logs.append("DEBUG: Starting Excel file generation")
            output = BytesIO()
            
            try:
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    workbook = writer.book
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D2E9'})
                    int_format = workbook.add_format({'num_format': '0'})

                    def write(df, sheet, selected_cols=None):
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

                    write(base_df[['Date', 'Code projet', 'Nom', 'Grade', 'Heures', 'Libelle projet']], '00_Base')
                    write(employee_summary, '01_Employee_Summary', ['Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Rate DES', 'Total', 'Total DES'])
                    write(global_summary, '02_Global_Summary', ['Libelle projet', 'Total Heures', 'Total', 'Total DES', 'Estimees'])
                    write(adjusted, '03_Adjusted', ['ID', 'Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Total', 'Adjusted Hours', 'Heures Retirées', 'Adjusted Cost'])
                    write(result, '04_Result', ['Libelle projet', 'Total Heures', 'Adjusted Hours', 'Heures Retirées', 'Adjusted Cost', 'Estimees', 'Ecart'])

                output.seek(0)
                now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"SLR_Facturation_{now_str}.xlsx"
                processing_logs.append(f"INFO: Excel file generated successfully: {filename}")

                # Save the initial Excel to the run directory
                initial_excel_filename = f"Initial_SLR_Report_{run_id[:8]}.xlsx"
                with open(run_dir / initial_excel_filename, 'wb') as f:
                    f.write(output.getvalue())
                processing_logs.append(f"INFO: Initial Excel saved as {initial_excel_filename}")

                # Store run_id and filename in session
                request.session['last_slr_run_id'] = run_id
                request.session['last_slr_run_heures_filename'] = heures_ibm_file_obj.name

                # Prepare context for the results page
                context = {
                    'form': SLRFileUploadForm(),  # Fresh form for a new upload
                    'page_title': 'Facturation SLR - Initial Report Generated',
                    'processing_logs': processing_logs,
                    'initial_report_generated': True,
                    'run_id': run_id,
                    'initial_excel_filename': initial_excel_filename,
                    'original_filename': filename
                }

                # Add success message
                messages.success(request, f"Initial report '{filename}' generated and saved. You can now review and make manual adjustments.")
                
                # Return the results page instead of the Excel file
                return render(request, 'billing/facturation_slr.html', context)

            except Exception as e:
                processing_logs.append(f"ERROR: Excel generation failed: {str(e)}")
                raise

        except Exception as e:
            processing_logs.append(f"ERROR: Exception during calculation: {str(e)}<br><pre>{traceback.format_exc()}</pre>")
            messages.error(request, f"An error occurred while generating the report: {str(e)}")
            context = {
                'form': form,
                'processing_logs': processing_logs,
                'page_title': 'Facturation SLR',
            }
            return render(request, 'billing/facturation_slr.html', context)

    # GET request or fallback
    context = {
        'form': form,
        'page_title': 'Facturation SLR',
        'processing_logs': processing_logs,
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

@login_required
def download_slr_report(request, run_id, filename):
    """View to download a generated SLR report."""
    try:
        file_path = TEMP_FILES_BASE_DIR / run_id / filename
        if not file_path.exists():
            messages.error(request, f"Report file not found: {filename}")
            return redirect('facturation_slr')
        
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except Exception as e:
        messages.error(request, f"Error downloading report: {str(e)}")
        return redirect('facturation_slr')

@login_required
def edit_slr_adjustments(request, run_id):
    """View to edit SLR adjustments."""
    try:
        run_dir = TEMP_FILES_BASE_DIR / run_id
        if not run_dir.exists():
            messages.error(request, f"Run directory not found for ID: {run_id}")
            return redirect('facturation_slr')

        # Load the necessary DataFrames
        adjusted_df = pd.read_parquet(run_dir / 'adjusted_initial.parquet')
        base_df = pd.read_parquet(run_dir / 'base_df.parquet')
        consultants_df = pd.read_parquet(run_dir / 'consultants_df.parquet')
        mafe_df = pd.read_parquet(run_dir / 'mafe_df.parquet')
        codes_df = pd.read_parquet(run_dir / 'codes_df.parquet')
        employee_summary = pd.read_parquet(run_dir / 'employee_summary_initial.parquet')
        global_summary = pd.read_parquet(run_dir / 'global_summary_initial.parquet')
        result = pd.read_parquet(run_dir / 'result_initial.parquet')

        # Remove technical columns from display
        display_columns = [col for col in adjusted_df.columns if col not in [
            'Total_Projet_Cout', 'coeff_total', 'total_rate_proj', 
            'priority_coeff', 'final_coeff'
        ]]
        display_df = adjusted_df[display_columns]

        if request.method == 'POST':
            # Handle form submission for adjustments
            try:
                # Get all adjusted hours from the form
                adjusted_hours = {}
                for key, value in request.POST.items():
                    if key.startswith('adjusted_hours_'):
                        index = int(key.split('_')[-1])
                        adjusted_hours[index] = float(value)

                # Update the adjusted DataFrame
                for index, hours in adjusted_hours.items():
                    adjusted_df.loc[index, 'Adjusted Hours'] = hours
                    adjusted_df.loc[index, 'Heures Retirées'] = adjusted_df.loc[index, 'Total Heures'] - hours
                    adjusted_df.loc[index, 'Adjusted Cost'] = hours * adjusted_df.loc[index, 'Rate']

                # Save the updated adjusted DataFrame
                adjusted_df.to_parquet(run_dir / 'adjusted_updated.parquet')

                # Recalculate the result DataFrame
                result = (
                    adjusted_df
                    .groupby('Libelle projet', as_index=False)
                    .agg({'Total Heures': 'sum', 'Adjusted Hours': 'sum', 'Adjusted Cost': 'sum', 'Heures Retirées': 'sum'})
                    .merge(global_summary[['Libelle projet', 'Estimees']], on='Libelle projet', how='left')
                )
                result['Ecart'] = result['Estimees'] - result['Adjusted Cost']

                # Save the updated result DataFrame
                result.to_parquet(run_dir / 'result_updated.parquet')

                # Generate a new Excel file with the updates
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    workbook = writer.book
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D2E9'})
                    int_format = workbook.add_format({'num_format': '0'})

                    def write(df, sheet, selected_cols=None):
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

                    write(base_df[['Date', 'Code projet', 'Nom', 'Grade', 'Heures', 'Libelle projet']], '00_Base')
                    write(employee_summary, '01_Employee_Summary', ['Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Rate DES', 'Total', 'Total DES'])
                    write(global_summary, '02_Global_Summary', ['Libelle projet', 'Total Heures', 'Total', 'Total DES', 'Estimees'])
                    write(adjusted_df, '03_Adjusted', ['ID', 'Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Total', 'Adjusted Hours', 'Heures Retirées', 'Adjusted Cost'])
                    write(result, '04_Result', ['Libelle projet', 'Total Heures', 'Adjusted Hours', 'Heures Retirées', 'Adjusted Cost', 'Estimees', 'Ecart'])

                output.seek(0)
                now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                updated_filename = f"SLR_Facturation_Updated_{now_str}.xlsx"
                
                # Save the updated Excel file
                with open(run_dir / updated_filename, 'wb') as f:
                    f.write(output.getvalue())

                messages.success(request, 'Adjustments saved successfully. You can download the updated report.')
                return redirect('download_slr_report', run_id=run_id, filename=updated_filename)

            except Exception as e:
                messages.error(request, f"Error saving adjustments: {str(e)}")
                return redirect('edit_slr_adjustments', run_id=run_id)

        # Prepare context for the edit page
        context = {
            'page_title': 'Edit SLR Adjustments',
            'run_id': run_id,
            'adjusted_df': display_df.to_dict('records'),
            'columns': display_df.columns.tolist(),
            'total_rows': len(display_df),
            'original_filename': request.session.get('last_slr_run_heures_filename', 'Unknown')
        }
        return render(request, 'billing/edit_slr_adjustments.html', context)

    except Exception as e:
        messages.error(request, f"Error loading adjustments: {str(e)}")
        return redirect('facturation_slr')