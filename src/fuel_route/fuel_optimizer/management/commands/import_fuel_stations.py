"""
Management command to import and clean fuel station data from CSV.

Features COMPLETE DATA CLEANING:
- Removes duplicate OPIS IDs (keeps cheapest price)
- Strips whitespace from all fields
- Validates price ranges (0-10 USD)
- Normalizes state codes (uppercase, 2 chars)
- Handles malformed data
- Rate limiting for geocoding
- Progress bar

Usage:
    python manage.py import_fuel_stations path/to/fuel-prices.csv
"""
import logging
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

from fuel_route.fuel_optimizer.models import FuelStation

logger = logging.getLogger('fuel_optimizer')


class Command(BaseCommand):
    help = 'Import fuel stations from CSV with COMPLETE data cleaning'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **options):
        csv_file = options['csv_file']

        self.stdout.write(self.style.WARNING(f'\n Loading CSV from: {csv_file}\n'))

        try:
            df = pd.read_csv(csv_file)
        except FileNotFoundError:
            raise CommandError(f' File not found: {csv_file}')
        except Exception as e:
            raise CommandError(f' Failed to parse CSV: {str(e)}')

        self.stdout.write(self.style.SUCCESS(f' Loaded {len(df)} rows from CSV\n'))

        # STEP 1: Clean column names
        df = self._clean_column_names(df)

        # STEP 2: Clean and validate data
        df = self._clean_data(df)

        # STEP 3: Handle duplicates (keep cheapest)
        df = self._handle_duplicates(df)

        # STEP 4: Validate required fields
        df = self._validate_required_fields(df)

        self.stdout.write(self.style.SUCCESS(
            f'\n After cleaning: {len(df)} valid stations\n'
        ))

        # STEP 5: Skip existing stations
        df = self._skip_existing_stations(df)

        if len(df) == 0:
            self.stdout.write(self.style.WARNING('  No new stations to import!\n'))
            return

        # STEP 6: Geocode if needed
        df = self._geocode_stations(df)

        # STEP 7: Import to database
        self._import_to_database(df)

        self.stdout.write(self.style.SUCCESS('\n Import completed successfully!\n'))

    # def _clean_column_names(self, df):
    #     """Clean and standardize column names"""
    #     self.stdout.write(' Step 1: Cleaning column names...')
        
    #     df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
    #     # Map common variations
    #     column_mapping = {
    #         'opis_truckstop_id': 'opis_id',
    #         'truckstop_name': 'name',
    #     }
    #     df.rename(columns=column_mapping, inplace=True)
        
    #     self.stdout.write(self.style.SUCCESS('   [OK] Column names cleaned\n'))
    #     return df

    # def _clean_data(self, df):
    #     """COMPLETE data cleaning"""
    #     self.stdout.write(' Step 2: Cleaning data fields...')
        
    #     initial_count = len(df)
        
    #     # Clean string fields
    #     string_columns = ['name', 'address', 'city', 'state']
    #     for col in string_columns:
    #         if col in df.columns:
    #             df[col] = df[col].astype(str).str.strip()
    #             df[col] = df[col].str.replace(r'\s+', ' ', regex=True)
        
    #     # Normalize state codes
    #     if 'state' in df.columns:
    #         df['state'] = df['state'].str.upper().str[:2]
    #         df = df[df['state'].str.match(r'^[A-Z]{2}$', na=False)]
        
    #     # Clean and validate price
    #     if 'retail_price' in df.columns:
    #         df['retail_price'] = pd.to_numeric(df['retail_price'], errors='coerce')
    #         df = df[(df['retail_price'] >= 0) & (df['retail_price'] <= 10)]
    #         df = df[df['retail_price'].notna()]
        
    #     # Clean OPIS ID
    #     if 'opis_id' in df.columns:
    #         df['opis_id'] = pd.to_numeric(df['opis_id'], errors='coerce')
    #         df = df[df['opis_id'].notna()]
    #         df['opis_id'] = df['opis_id'].astype(int)
        
    #     removed = initial_count - len(df)
    #     if removed > 0:
    #         self.stdout.write(self.style.WARNING(
    #             f'     Removed {removed} rows with invalid data'
    #         ))
    #     self.stdout.write(self.style.SUCCESS('   [OK] Data cleaned\n'))
        
    #     return df

    # def _handle_duplicates(self, df):
    #     """Handle duplicate OPIS IDs - keep cheapest price"""
    #     self.stdout.write(' Step 3: Handling duplicates...')
        
    #     initial_count = len(df)
        
    #     # Sort by price (cheapest first) and remove duplicates
    #     df = df.sort_values('retail_price', ascending=True)
    #     df = df.drop_duplicates(subset=['opis_id'], keep='first')
        
    #     removed = initial_count - len(df)
    #     if removed > 0:
    #         self.stdout.write(self.style.WARNING(
    #             f'     Removed {removed} duplicate stations (kept cheapest prices)'
    #         ))
    #     self.stdout.write(self.style.SUCCESS('   [OK] Duplicates handled\n'))
        
    #     return df

    # def _validate_required_fields(self, df):
    #     """Validate all required fields are present"""
    #     self.stdout.write('[OK]  Step 4: Validating required fields...')
        
    #     required_fields = ['opis_id', 'name', 'city', 'state', 'retail_price']
    #     missing_fields = [f for f in required_fields if f not in df.columns]
        
    #     if missing_fields:
    #         raise CommandError(
    #             f' Missing required columns: {", ".join(missing_fields)}'
    #         )
        
    #     initial_count = len(df)
    #     df = df.dropna(subset=required_fields)
        
    #     removed = initial_count - len(df)
    #     if removed > 0:
    #         self.stdout.write(self.style.WARNING(
    #             f'     Removed {removed} rows with missing required fields'
    #         ))
    #     self.stdout.write(self.style.SUCCESS('   [OK] Required fields validated\n'))
        
    #     return df

    # def _skip_existing_stations(self, df):
    #     """Skip stations already in database"""
    #     self.stdout.write(' Step 5: Checking for existing stations...')
        
    #     csv_ids = df['opis_id'].tolist()
    #     existing_ids = set(
    #         FuelStation.objects.filter(opis_id__in=csv_ids).values_list(
    #             'opis_id', flat=True
    #         )
    #     )
        
    #     initial_count = len(df)
    #     df = df[~df['opis_id'].isin(existing_ids)]
        
    #     skipped = initial_count - len(df)
    #     if skipped > 0:
    #         self.stdout.write(self.style.WARNING(
    #             f'   [OK]  Skipping {skipped} existing stations'
    #         ))
    #     self.stdout.write(self.style.SUCCESS(f'   [OK] {len(df)} new stations to process\n'))
        
    #     return df

    # def _geocode_stations(self, df):
    #     """Geocode stations to get lat/lon coordinates"""
    #     self.stdout.write(' Step 6: Geocoding stations...')
    #     self.stdout.write('   This may take 5-10 minutes for all stations\n')
        
    #     # Check if lat/lon already in CSV
    #     if 'latitude' in df.columns and 'longitude' in df.columns:
    #         self.stdout.write('     Using existing lat/lon from CSV')
    #         df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    #         df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    #         df = df[df['latitude'].notna() & df['longitude'].notna()]
    #         df = df[(df['latitude'] >= -90) & (df['latitude'] <= 90)]
    #         df = df[(df['longitude'] >= -180) & (df['longitude'] <= 180)]
    #         self.stdout.write(self.style.SUCCESS('   [OK] Coordinates validated\n'))
    #         return df
        
    #     # Initialize geocoder with rate limiting
    #     geolocator = Nominatim(user_agent='fuel_route_optimizer_v1', timeout=10)
    #     geocode = RateLimiter(
    #         geolocator.geocode,
    #         min_delay_seconds=1,
    #         max_retries=2
    #     )
        
    #     geocoded_data = []
    #     failed_count = 0
        
    #     for idx, row in df.iterrows():
    #         try:
    #             address = f"{row['city']}, {row['state']}, USA"
    #             location = geocode(address)
                
    #             if location:
    #                 row['latitude'] = location.latitude
    #                 row['longitude'] = location.longitude
    #                 geocoded_data.append(row)
    #             else:
    #                 failed_count += 1
            
    #         except (GeocoderTimedOut, GeocoderServiceError):
    #             failed_count += 1
            
    #         # Progress indicator
    #         if (idx + 1) % 100 == 0:
    #             self.stdout.write(f'    Geocoded {idx + 1}/{len(df)} stations...')
        
    #     if failed_count > 0:
    #         self.stdout.write(self.style.WARNING(
    #             f'\n     Failed to geocode {failed_count} stations'
    #         ))
        
    #     self.stdout.write(self.style.SUCCESS(
    #         f'   [OK] Successfully geocoded {len(geocoded_data)} stations\n'
    #     ))
        
    #     return pd.DataFrame(geocoded_data)

    def _import_to_database(self, df):
        """Import cleaned data to database"""
        self.stdout.write(f' Step 7: Importing {len(df)} stations to database...')
        
        stations = []
        skipped = 0
        
        for _, row in df.iterrows():
            try:
                station = FuelStation(
                    opis_id=int(row['opis_id']),
                    name=row['name'][:200],
                    address=row.get('address', '')[:300],
                    city=row['city'][:100],
                    state=row['state'][:2],
                    retail_price=Decimal(str(row['retail_price'])),
                    latitude=Decimal(str(row['latitude'])),
                    longitude=Decimal(str(row['longitude'])),
                )
                stations.append(station)
            except (ValueError, InvalidOperation, KeyError) as e:
                skipped += 1
        
        if skipped > 0:
            self.stdout.write(self.style.WARNING(
                f'     Skipped {skipped} invalid rows'
            ))
        
        # Bulk create for performance (1000 records per batch)
        FuelStation.objects.bulk_create(stations, batch_size=1000)
        
        self.stdout.write(self.style.SUCCESS(
            f'   [OK] Successfully imported {len(stations)} fuel stations'
        ))