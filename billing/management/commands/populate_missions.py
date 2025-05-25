import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from billing.models import Mission
import os

class Command(BaseCommand):
    help = 'Populates the Mission database from a specified Excel file (sheet "Subset").'

    def add_arguments(self, parser):
        parser.add_argument('excel_file_path', type=str, help='The full path to the Excel file.')

    def handle(self, *args, **options):
        excel_file_path = options['excel_file_path']

        if not os.path.exists(excel_file_path):
            raise CommandError(f'Error: Excel file not found at path: {excel_file_path}')

        self.stdout.write(f"Starting to populate missions from: {excel_file_path}")

        try:
            # Read the specified sheet from the Excel file
            df = pd.read_excel(excel_file_path, sheet_name='Subset')
            self.stdout.write(f"Successfully read sheet 'Subset'. Found {len(df)} rows.")
        except Exception as e:
            raise CommandError(f"Error reading Excel file or sheet 'Subset': {e}")

        created_count = 0
        updated_count = 0

        # Define expected Excel column names (adjust if they are slightly different in the file)
        col_swift_code = "SWIFT Code"
        col_libelle_projet_excel = "Libelle Projet "  # Name in Excel
        col_comment_excel = "Comment"
        col_customer_name_excel = "Customer Name"

        # Verify necessary columns exist
        required_cols = [col_swift_code, col_libelle_projet_excel, col_comment_excel, col_customer_name_excel]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise CommandError(f"Missing required columns in Excel sheet 'Subset': {', '.join(missing_cols)}")

        for index, row in df.iterrows():
            try:
                otp_l2_value = str(row[col_swift_code]).strip()
                # Keep skipping if otp_l2 (primary lookup key) is essentially empty
                if not otp_l2_value or otp_l2_value.lower() == 'nan' or pd.isna(row[col_swift_code]):
                    self.stdout.write(self.style.WARNING(f"Skipping row {index+2} due to empty or invalid SWIFT Code: '{row[col_swift_code]}'"))
                    continue

                # For Libelle Projet: fallback to "" if Excel cell is empty/NaN
                libelle_projet_value = str(row[col_libelle_projet_excel]).strip() if pd.notna(row[col_libelle_projet_excel]) else ""
                if libelle_projet_value.lower() == 'nan':  # Catch if str(np.nan) or similar became "nan"
                    libelle_projet_value = ""

                # Comment to code_type logic (already handles empty by defaulting, which is good)
                comment_value_excel = str(row[col_comment_excel]).strip() if pd.notna(row[col_comment_excel]) else ""
                code_type_value_db = Mission.CODE_FRANCE  # Default
                if comment_value_excel.upper() == 'CODE DES':
                    code_type_value_db = Mission.CODE_DES

                # For Customer name (mapping to belgian_name): fallback to "" if Excel cell is empty/NaN
                belgian_name_value = str(row[col_customer_name_excel]).strip() if pd.notna(row[col_customer_name_excel]) else ""
                if belgian_name_value.lower() == 'nan':  # Catch if str(np.nan) or similar became "nan"
                    belgian_name_value = ""

                mission, created = Mission.objects.update_or_create(
                    otp_l2=otp_l2_value,
                    defaults={
                        'libelle_de_projet': libelle_projet_value,
                        'code_type': code_type_value_db,
                        'belgian_name': belgian_name_value,
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Created Mission: {mission.otp_l2} - {mission.libelle_de_projet}"))
                else:
                    updated_count += 1
                    self.stdout.write(f"Updated Mission: {mission.otp_l2} - {mission.libelle_de_projet}")

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error processing row {index + 2}: {row.to_dict()}. Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Mission population complete. Created: {created_count}, Updated: {updated_count}.")) 