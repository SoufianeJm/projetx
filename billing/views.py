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
                base_df = pd.read_excel(heures_ibm_file_obj, sheet_name='base', usecols="E,H,I,M,N")
                base_df.columns = ['Code projet', 'Nom', 'Grade', 'Date', 'Heures']
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

                # --- MATCH main.py LOGIC ---
                # 1. Prepare base_df (Heures IBM)
                base_df = pd.read_excel(heures_ibm_file_obj, sheet_name='base', usecols="E,H,I,M,N")
                base_df.columns = ['Code projet', 'Nom', 'Grade', 'Date', 'Heures']

                # 2. Prepare codes_df from Mission model
                codes_qs = Mission.objects.all().values('otp_l2', 'libelle_de_projet')
                codes_df = pd.DataFrame(list(codes_qs))
                codes_df = codes_df.rename(columns={'otp_l2': 'Code projet', 'libelle_de_projet': 'Libelle projet'})
                codes_df['Libelle projet'] = codes_df['Libelle projet'].fillna('Code France')
                base_df = base_df.merge(codes_df[['Code projet', 'Libelle projet']], on='Code projet', how='left')

                # 3. Prepare consultants_df from Resource model
                consultants_qs = Resource.objects.all().values('full_name', 'rate_ibm', 'rate_des', 'grade')
                consultants_df = pd.DataFrame(list(consultants_qs))
                consultants_df = consultants_df.rename(columns={'full_name': 'Nom', 'rate_ibm': 'Rate', 'rate_des': 'Rate DES', 'grade': 'Grade'})
                base_df['Nom'] = base_df['Nom'].astype(str).str.lower().str.strip()
                consultants_df['Nom'] = consultants_df['Nom'].astype(str).str.lower().str.strip()
                base_df['Heures'] = pd.to_numeric(base_df['Heures'], errors='coerce').fillna(0)
                consultants_df['Rate'] = pd.to_numeric(consultants_df['Rate'], errors='coerce').fillna(0)
                consultants_df['Rate DES'] = pd.to_numeric(consultants_df['Rate DES'], errors='coerce').fillna(0)

                # 4. Prepare MAFE file as in main.py
                mafe_file_obj.seek(0)
                mafe_raw = pd.read_excel(mafe_file_obj, sheet_name='(Tab A) FULLY COMMITTED', header=None)
                mafe_raw.columns = mafe_raw.iloc[14].astype(str).str.strip().str.replace('\n', ' ').str.replace('\r', ' ')
                mafe = mafe_raw.drop(index=list(range(0, 15))).reset_index(drop=True)

                # 5. Find forecast column in MAFE
                mois_mapping = {
                    'Janvier': 'Jan', 'Février': 'Feb', 'Mars': 'Mar', 'Avril': 'Apr', 'Mai': 'May', 'Juin': 'Jun',
                    'Juillet': 'Jul', 'Août': 'Aug', 'Septembre': 'Sep', 'Octobre': 'Oct', 'Novembre': 'Nov', 'Décembre': 'Dec',
                    'Jan': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Apr', 'May': 'May', 'Jun': 'Jun',
                    'Jul': 'Jul', 'Aug': 'Aug', 'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dec'
                }
                match = re.search(r'(Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\d]*(\d{2,4})', heures_ibm_file_obj.name)
                mois = mois_mapping.get(match.group(1), match.group(1)) if match else ''
                annee = match.group(2) if match else ''
                forecast_col_cleaned = next((col for col in mafe.columns if mois in col and 'Forecasts' in col and annee[-2:] in col), None)
                if forecast_col_cleaned:
                    mafe_subset = mafe[['Country', 'Customer Name', forecast_col_cleaned]].rename(columns={forecast_col_cleaned: 'Estimees'})
                    # No MAFE traitement model, so skip merge with Belgian Name
                    mafe_subset['Libelle projet'] = mafe_subset['Customer Name']
                else:
                    mafe_subset = pd.DataFrame(columns=["Country", "Customer Name", "Libelle projet", "Estimees"])

                # 6. Employee summary
                employee_summary = (
                    base_df.groupby(['Libelle projet', 'Nom', 'Grade'], as_index=False)
                    .agg({'Heures': 'sum'})
                    .rename(columns={'Heures': 'Total Heures'})
                    .merge(consultants_df[['Nom', 'Rate', 'Rate DES']], on='Nom', how='left')
                )
                employee_summary['Total'] = employee_summary['Rate'] * employee_summary['Total Heures']
                employee_summary['Total DES'] = employee_summary['Rate DES'] * employee_summary['Total Heures']

                summary_by_proj = employee_summary.groupby('Libelle projet', as_index=False).agg({'Total Heures': 'sum', 'Total': 'sum', 'Total DES': 'sum'})
                global_summary = pd.merge(mafe_subset[['Libelle projet', 'Estimees']].drop_duplicates(), summary_by_proj, on='Libelle projet', how='left')
                global_summary[['Total Heures', 'Total', 'Total DES']] = global_summary[['Total Heures', 'Total', 'Total DES']].fillna(0)
                global_summary['Estimees'] = pd.to_numeric(global_summary['Estimees'].astype(str).str.strip().replace(['', '-', 'nan', 'None'], '0'), errors='coerce').fillna(0)

                adjusted = employee_summary.merge(global_summary[['Libelle projet', 'Estimees']], on='Libelle projet', how='left')
                adjusted['Total_Projet_Cout'] = adjusted.groupby('Libelle projet')['Total'].transform('sum')
                adjusted['total_rate_proj'] = adjusted.groupby('Libelle projet')['Rate'].transform('sum')
                adjusted = adjusted[(adjusted['Total_Projet_Cout'] > 0) & (adjusted['total_rate_proj'] > 0)]
                adjusted['coeff_total'] = adjusted['Estimees'] / adjusted['Total_Projet_Cout']
                adjusted['priority_coeff'] = adjusted['Rate'] / adjusted['total_rate_proj']
                adjusted['final_coeff'] = adjusted['coeff_total'] * adjusted['priority_coeff']
                adjusted['Adjusted Hours'] = (adjusted['Total Heures'] * (1 - adjusted['final_coeff'])).round()
                adjusted['Adjusted Hours'] = adjusted['Adjusted Hours'].apply(lambda x: max(x, 0))
                adjusted['Heures Retirées'] = adjusted['Total Heures'] - adjusted['Adjusted Hours']
                adjusted['Adjusted Cost'] = adjusted['Adjusted Hours'] * adjusted['Rate']
                adjusted['ID'] = adjusted['Nom'].astype(str) + ' - ' + adjusted['Libelle projet'].astype(str)
                cols = ['ID'] + [col for col in adjusted.columns if col != 'ID']
                adjusted = adjusted[cols]

                result = (
                    adjusted.groupby('Libelle projet', as_index=False)
                    .agg({'Total Heures': 'sum', 'Adjusted Hours': 'sum', 'Adjusted Cost': 'sum'})
                    .merge(global_summary[['Libelle projet', 'Estimees']], on='Libelle projet', how='left')
                )
                result['Ecart'] = result['Estimees'] - result['Adjusted Cost']

                for df in [employee_summary, global_summary, adjusted, result]:
                    for col in df.select_dtypes(include='number').columns:
                        df[col] = df[col].round(0)

                # --- Excel Output Block ---
                try:
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
                        write(adjusted, '03_Adjusted', ['ID', 'Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Total', 'Adjusted Hours', 'Heures Retirées', 'Adjusted Cost'])
                        write(result, '04_Result')

                    output.seek(0)
                    now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"SLR_Facturation_{now_str}.xlsx"
                    processing_logs.append(f"INFO: Excel file generated with sheets: 00_Base, 01_Employee_Summary, 02_Global_Summary, 03_Adjusted, 04_Result")

                    response = HttpResponse(
                        output.getvalue(),
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response
                except Exception as e:
                    processing_logs.append(f"ERROR: Failed to generate Excel file: {str(e)}<br><pre>{traceback.format_exc()}</pre>")
                    # Fall through to render logs

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