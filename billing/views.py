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

# Create your views here.

@login_required
def home(request):
    resources = Resource.objects.all()
    missions = Mission.objects.all()
    context = {
        'resources': resources,
        'missions': missions,
    }
    return render(request, 'billing/home.html', context)

# Resource CRUD Views
class ResourceCreateView(LoginRequiredMixin, CreateView):
    model = Resource
    form_class = ResourceForm
    template_name = 'billing/generic_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create New Resource'
        context['form_title'] = 'Add Resource'
        return context

class ResourceUpdateView(LoginRequiredMixin, UpdateView):
    model = Resource
    form_class = ResourceForm
    template_name = 'billing/generic_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Update Resource'
        context['form_title'] = f"Edit Resource: {self.object.full_name}"
        return context

class ResourceDeleteView(LoginRequiredMixin, DeleteView):
    model = Resource
    template_name = 'billing/generic_confirm_delete.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Delete Resource'
        context['item_name'] = self.object.full_name
        return context

# Mission CRUD Views
class MissionCreateView(LoginRequiredMixin, CreateView):
    model = Mission
    form_class = MissionForm
    template_name = 'billing/generic_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create New Mission'
        context['form_title'] = 'Add Mission'
        return context

class MissionUpdateView(LoginRequiredMixin, UpdateView):
    model = Mission
    form_class = MissionForm
    template_name = 'billing/generic_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Update Mission'
        context['form_title'] = f"Edit Mission: {self.object.otp_l2}"
        return context

class MissionDeleteView(LoginRequiredMixin, DeleteView):
    model = Mission
    template_name = 'billing/generic_confirm_delete.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Delete Mission'
        context['item_name'] = self.object.otp_l2
        return context

@login_required
def facturation_slr_view(request):
    if request.method == 'POST':
        form = SLRFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            mafe_file_obj = request.FILES['mafe_report_file']
            heures_ibm_file_obj = request.FILES['heures_ibm_file']

            try:
                # Extract month and year from "Heures IBM" filename
                heures_filename = heures_ibm_file_obj.name
                mois_mapping = {
                    'Janvier': 'Jan', 'Février': 'Feb', 'Mars': 'Mar', 'Avril': 'Apr', 'Mai': 'May', 'Juin': 'Jun',
                    'Juillet': 'Jul', 'Août': 'Aug', 'Septembre': 'Sep', 'Octobre': 'Oct', 'Novembre': 'Nov', 'Décembre': 'Dec',
                    'Jan': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Apr', 'May': 'May', 'Jun': 'Jun',
                    'Jul': 'Jul', 'Aug': 'Aug', 'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dec'
                }
                
                match = re.search(r'(Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\d]*(\d{2,4})', heures_filename, re.IGNORECASE)
                if not match:
                    messages.error(request, f"Could not parse month/year from Heures IBM filename: {heures_filename}")
                    return render(request, 'billing/facturation_slr.html', {'form': form})

                parsed_mois_nom = match.group(1).capitalize()
                parsed_annee_short = match.group(2)
                current_century = str(datetime.now().year // 100)
                parsed_annee_full = current_century + parsed_annee_short if len(parsed_annee_short) == 2 else parsed_annee_short

                # Read "Heures IBM" file
                df_heures_ibm = pd.read_excel(heures_ibm_file_obj, sheet_name='base', usecols="E,H,I,N")
                df_heures_ibm.columns = ['Code projet', 'Nom Complet', 'Grade', 'Heures Déclarées']
                df_heures_ibm['Nom Complet'] = df_heures_ibm['Nom Complet'].astype(str).str.lower().str.strip()
                df_heures_ibm['Heures Déclarées'] = pd.to_numeric(df_heures_ibm['Heures Déclarées'], errors='coerce').fillna(0)

                # Get Resource and Mission data from Django DB
                db_resources = pd.DataFrame.from_records(
                    Resource.objects.all().values('full_name', 'rank', 'rate_ibm', 'rate_des')
                )
                db_resources.rename(columns={
                    'full_name': 'Nom Complet DB',
                    'rank': 'Rank DB',
                    'rate_ibm': 'Rate IBM DB',
                    'rate_des': 'Rate DES DB'
                }, inplace=True)
                db_resources['Nom Complet DB'] = db_resources['Nom Complet DB'].astype(str).str.lower().str.strip()

                db_missions = pd.DataFrame.from_records(
                    Mission.objects.all().values('otp_l2', 'belgian_name', 'libelle_de_projet')
                )
                db_missions.rename(columns={
                    'otp_l2': 'Code projet DB',
                    'libelle_de_projet': 'Libellé Projet DB'
                }, inplace=True)

                # Merge data
                df_merged = pd.merge(df_heures_ibm, db_missions, left_on='Code projet', right_on='Code projet DB', how='left')
                
                # Aggregate hours
                df_agg_hours = df_merged.groupby(['Libellé Projet DB', 'Nom Complet', 'Grade'], as_index=False).agg(
                    {'Heures Déclarées': 'sum'}
                ).rename(columns={'Heures Déclarées': 'Total Heures'})

                # Merge with Resources
                final_df = pd.merge(df_agg_hours, db_resources, left_on='Nom Complet', right_on='Nom Complet DB', how='left')

                # Calculate totals
                final_df['Total IBM'] = final_df['Total Heures'] * final_df['Rate IBM DB']
                final_df['Total DES'] = final_df['Total Heures'] * final_df['Rate DES DB']

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
                output_excel = BytesIO()
                with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
                    output_df.to_excel(writer, sheet_name='Facturation_SLR', index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Facturation_SLR']
                    
                    # Format headers
                    header_format = workbook.add_format({
                        'bold': True,
                        'text_wrap': True,
                        'valign': 'top',
                        'fg_color': '#D7E4BC',
                        'border': 1
                    })
                    
                    # Apply formatting
                    for col_num, value in enumerate(output_df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                        worksheet.set_column(col_num, col_num, len(value) + 5)

                output_excel.seek(0)
                response = HttpResponse(
                    output_excel,
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="SLR_Facturation_Output_{parsed_mois_nom}_{parsed_annee_full}.xlsx"'
                messages.success(request, "Report generated successfully!")
                return response

            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
                return render(request, 'billing/facturation_slr.html', {'form': form})

    else:
        form = SLRFileUploadForm()
    
    return render(request, 'billing/facturation_slr.html', {
        'form': form,
        'page_title': 'Facturation SLR'
    })
