"""
Script optimisé pour géocoder uniquement les stations valides.
Applique le même nettoyage que Django AVANT le géocodage.
"""
import pandas as pd
import requests
import time
import os
from dotenv import load_dotenv

# Charger la clé API
load_dotenv()
MAPQUEST_API_KEY = os.getenv('MAPQUEST_API_KEY', '')

if not MAPQUEST_API_KEY:
    print("❌ ERREUR: MAPQUEST_API_KEY non trouvée dans .env")
    exit(1)

def clean_data(df):
    """Applique le même nettoyage que Django"""
    print("\n🧹 Nettoyage des données (comme Django)...")
    initial_count = len(df)
    
    # Nettoyer les noms de colonnes
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    # Mapper les variations
    column_mapping = {
        'opis_truckstop_id': 'opis_id',
        'truckstop_name': 'name',
    }
    df.rename(columns=column_mapping, inplace=True)
    
    # Nettoyer les champs texte
    string_columns = ['name', 'address', 'city', 'state']
    for col in string_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].str.replace(r'\s+', ' ', regex=True)
    
    # Valider les états (2 lettres majuscules)
    if 'state' in df.columns:
        df['state'] = df['state'].str.upper().str[:2]
        df = df[df['state'].str.match(r'^[A-Z]{2}$', na=False)]
    
    # Valider les prix (0-10 USD)
    if 'retail_price' in df.columns:
        df['retail_price'] = pd.to_numeric(df['retail_price'], errors='coerce')
        df = df[(df['retail_price'] >= 0) & (df['retail_price'] <= 10)]
        df = df[df['retail_price'].notna()]
    
    # Valider OPIS ID
    if 'opis_id' in df.columns:
        df['opis_id'] = pd.to_numeric(df['opis_id'], errors='coerce')
        df = df[df['opis_id'].notna()]
        df['opis_id'] = df['opis_id'].astype(int)
    
    # Supprimer les doublons (garder le moins cher)
    df = df.sort_values('retail_price', ascending=True)
    df = df.drop_duplicates(subset=['opis_id'], keep='first')
    
    # Valider les champs requis
    required_fields = ['opis_id', 'name', 'address', 'city', 'state', 'retail_price']
    df = df.dropna(subset=required_fields)
    
    removed = initial_count - len(df)
    print(f"   ✓ Nettoyage terminé")
    print(f"   • Lignes initiales: {initial_count}")
    print(f"   • Lignes valides: {len(df)}")
    print(f"   • Lignes supprimées: {removed} ({removed/initial_count*100:.1f}%)\n")
    
    return df

def geocode_address(address, city, state):
    """Géocode une adresse complète avec MapQuest"""
    full_address = f"{address}, {city}, {state}, USA"
    
    url = "http://www.mapquestapi.com/geocoding/v1/address"
    params = {
        'key': MAPQUEST_API_KEY,
        'location': full_address
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('results') and data['results'][0].get('locations'):
            location = data['results'][0]['locations'][0]
            lat_lng = location.get('latLng', {})
            quality = location.get('geocodeQuality', '')
            
            if lat_lng.get('lat') and lat_lng.get('lng'):
                return lat_lng['lat'], lat_lng['lng'], quality
                
    except Exception as e:
        pass  # Silencieux pour ne pas polluer la console
    
    return None, None, None

# ============ SCRIPT PRINCIPAL ============

print("\n" + "="*60)
print("  GÉOCODAGE OPTIMISÉ DES STATIONS-SERVICE")
print("="*60)

# Charger le CSV
print("\n📂 Chargement du CSV...")
df = pd.read_csv('fuel-prices-for-be-assessment.csv')
print(f"   ✓ {len(df)} stations chargées")

# NETTOYER AVANT DE GÉOCODER (économise temps + API calls)
df = clean_data(df)

# Initialiser les nouvelles colonnes
df['latitude'] = None
df['longitude'] = None
df['geocode_quality'] = None

# Compteurs
success_count = 0
failed_count = 0
start_time = time.time()

print("🌍 Géocodage en cours...")
print(f"   {len(df)} stations à géocoder (~{int(len(df)*0.21/60)} minutes)\n")

# Géocoder chaque station VALIDE
for idx, row in df.iterrows():
    address = str(row['address'])
    city = str(row['city'])
    state = str(row['state'])
    
    lat, lng, quality = geocode_address(address, city, state)
    
    if lat and lng:
        df.at[idx, 'latitude'] = lat
        df.at[idx, 'longitude'] = lng
        df.at[idx, 'geocode_quality'] = quality
        success_count += 1
    else:
        failed_count += 1
    
    # Progression tous les 100
    if (success_count + failed_count) % 100 == 0:
        elapsed = time.time() - start_time
        rate = (success_count + failed_count) / elapsed
        remaining = (len(df) - success_count - failed_count) / rate
        
        print(f"   [{success_count + failed_count}/{len(df)}] "
              f"✓ {success_count} | ✗ {failed_count} | "
              f"Reste: ~{int(remaining/60)}min {int(remaining%60)}s")
    
    time.sleep(0.21)  # Respecter limite MapQuest

# Statistiques finales
total_time = time.time() - start_time
print(f"\n{'='*60}")
print(f"✅ TERMINÉ en {int(total_time/60)}min {int(total_time%60)}s")
print(f"{'='*60}")
print(f"   Géocodage réussi: {success_count}/{len(df)} ({success_count/len(df)*100:.1f}%)")
print(f"   Échecs: {failed_count}")
print(f"{'='*60}\n")

# Sauvegarder
output_file = 'fuel-prices-with-coordinates.csv'
df.to_csv(output_file, index=False)

print(f"💾 Sauvegardé: {output_file}")
print(f"\n📊 Aperçu:")
print(df[['name', 'city', 'state', 'retail_price', 'latitude', 'longitude']].head(3))

print(f"\n✅ PRÊT pour Django (import sera instantané):")
print(f"   cd src/fuel_route")
print(f"   python manage.py import_fuel_stations ../../{output_file}\n")