import os 
import re
import shutil
import time
import pandas as pd
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 📁 Chemins
folder_path = r'C:\Users\samadane\OneDrive - Deloitte (O365D)\SLR_FACTURATION_15052025'
output_path = os.path.join(folder_path, 'Output.xlsx')
draft_folder = os.path.join(folder_path, 'draft')
logs_folder = os.path.join(folder_path, 'Logs')
log_file = os.path.join(logs_folder, 'Projet_Facturation_Log.txt')

os.makedirs(draft_folder, exist_ok=True)
os.makedirs(logs_folder, exist_ok=True)

def safe_read_excel(path, **kwargs):
    for _ in range(5):
        try:
            return pd.read_excel(path, **kwargs)
        except PermissionError:
            print(f"⏳ Fichier verrouillé : {os.path.basename(path)}... nouvelle tentative dans 2s")
            time.sleep(2)
    raise PermissionError(f"⛔ Fichier toujours verrouillé : {path}")

def recalculer():
    try:
        print("🔁 Lancement du recalcul...")

        # 🕒 Initialisation
        date_suffix = datetime.now().strftime('%d%m%Y_%H%M%S')
        now = datetime.now()

        if os.path.exists(output_path):
            backup_path = os.path.join(draft_folder, f"Output__{date_suffix}.xlsx")
            shutil.copy2(output_path, backup_path)

        fichiers = os.listdir(folder_path)
        heures_file = next((f for f in fichiers if "IBM" in f and f.endswith(('.xlsx', '.xls')) and ("Heures" in f or f.startswith("IBM"))), None)
        mafe_file = next((f for f in fichiers if f.startswith('DTT IMT France MAFE Report -') and f.endswith(('.xlsx', '.xls'))), None)
        traitement_file = next((f for f in fichiers if 'Fichier de traitement' in f and f.endswith(('.xlsx', '.xls'))), None)

        if not heures_file or not mafe_file or not traitement_file:
            raise FileNotFoundError("Un ou plusieurs fichiers requis sont introuvables.")

        heures_path = os.path.join(folder_path, heures_file)
        mafe_path = os.path.join(folder_path, mafe_file)
        traitement_path = os.path.join(folder_path, traitement_file)

        mois_mapping = {
            'Janvier': 'Jan', 'Février': 'Feb', 'Mars': 'Mar', 'Avril': 'Apr', 'Mai': 'May', 'Juin': 'Jun',
            'Juillet': 'Jul', 'Août': 'Aug', 'Septembre': 'Sep', 'Octobre': 'Oct', 'Novembre': 'Nov', 'Décembre': 'Dec',
            'Jan': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Apr', 'May': 'May', 'Jun': 'Jun',
            'Jul': 'Jul', 'Aug': 'Aug', 'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dec'
        }
        match = re.search(r'(Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\d]*(\d{2,4})', heures_file)
        mois = mois_mapping.get(match.group(1), match.group(1))
        annee = match.group(2)

        base = safe_read_excel(heures_path, sheet_name='base', usecols="E,H,I,M,N")
        base.columns = ['Code projet', 'Nom', 'Grade', 'Date', 'Heures']
        codes = safe_read_excel(traitement_path, sheet_name='codes', usecols="A:C").fillna({'Libelle projet': 'Code France'})
        codes.columns = ['Code projet', 'Libelle projet', 'Commentaire']
        base = base.merge(codes[['Code projet', 'Libelle projet']], on='Code projet', how='left')

        consultants = safe_read_excel(traitement_path, sheet_name='Consultants', usecols="C,D,E,I")
        consultants.columns = ['Nom', 'Rate', 'Rate DES', 'Grade']
        base['Nom'] = base['Nom'].astype(str).str.lower().str.strip()
        consultants['Nom'] = consultants['Nom'].astype(str).str.lower().str.strip()
        base['Heures'] = pd.to_numeric(base['Heures'], errors='coerce').fillna(0)
        consultants['Rate'] = pd.to_numeric(consultants['Rate'], errors='coerce').fillna(0)
        consultants['Rate DES'] = pd.to_numeric(consultants['Rate DES'], errors='coerce').fillna(0)

        mafe_raw = safe_read_excel(mafe_path, sheet_name='(Tab A) FULLY COMMITTED', header=None)
        mafe_raw.columns = mafe_raw.iloc[14].astype(str).str.strip().str.replace('\n', ' ').str.replace('\r', ' ')
        mafe = mafe_raw.drop(index=list(range(0, 15))).reset_index(drop=True)
        mafe_traitement = safe_read_excel(traitement_path, sheet_name='MAFE')

        forecast_col_cleaned = next((col for col in mafe.columns if mois in col and 'Forecasts' in col and annee[-2:] in col), None)
        if forecast_col_cleaned:
            mafe_subset = mafe[['Country', 'Customer Name', forecast_col_cleaned]].rename(columns={forecast_col_cleaned: 'Estimees'})
            mafe_subset = mafe_subset.merge(mafe_traitement[['Customer Name', 'Belgian Name']], on='Customer Name', how='left')
            mafe_subset = mafe_subset.rename(columns={'Belgian Name': 'Libelle projet'})
            mafe_subset['Libelle projet'] = mafe_subset['Libelle projet'].fillna(mafe_subset['Customer Name'])
        else:
            mafe_subset = pd.DataFrame(columns=["Country", "Customer Name", "Libelle projet", "Estimees"])

        employee_summary = (
            base.groupby(['Libelle projet', 'Nom', 'Grade'], as_index=False)
            .agg({'Heures': 'sum'})
            .rename(columns={'Heures': 'Total Heures'})
            .merge(consultants[['Nom', 'Rate']], on='Nom', how='left')
            .merge(consultants[['Nom', 'Rate DES']], on='Nom', how='left')
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

        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
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

            write(base[['Date', 'Code projet', 'Nom', 'Grade', 'Heures', 'Libelle projet']], '00_Base')
            write(employee_summary, '01_Employee_Summary', ['Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Rate DES', 'Total', 'Total DES'])
            write(global_summary, '02_Global_Summary', ['Libelle projet', 'Total Heures', 'Total', 'Total DES', 'Estimees'])
            write(adjusted, '03_Adjusted', ['ID', 'Libelle projet', 'Nom', 'Grade', 'Total Heures', 'Rate', 'Total', 'Adjusted Hours', 'Heures Retirées', 'Adjusted Cost'])
            write(result, '04_Result')

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] ✅ Export vers : {os.path.basename(output_path)}\n")

        print(f"✅ Script terminé. Fichier généré : {os.path.basename(output_path)}")

    except Exception as e:
        print("\n⛔ ERREUR GLOBALE :", str(e))


# 👀 Détection de changement sur Output.xlsx
class ChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("Output.xlsx"):
            print(f"\n📌 Modification détectée sur Output.xlsx ({datetime.now().strftime('%H:%M:%S')})")
            recalculer()

if __name__ == "__main__":
    print("👁️ Surveillance de Output.xlsx... (Ctrl+C pour quitter)")
    observer = Observer()
    observer.schedule(ChangeHandler(), path=folder_path, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()