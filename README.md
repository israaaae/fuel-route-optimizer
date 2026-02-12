# 🚗⛽ Fuel Route Optimizer API

Django REST API for optimal fuel route planning within the USA.

## ✨ Features

✅ **Single API Call**: MapQuest API (geocoding + routing in ONE call)  
✅ **Smart Fuel Optimization**: Deviation scoring + bounding box filtering  
✅ **Complete Data Cleaning**: Handles duplicates, invalid prices, missing data ...  
✅ **Fast Performance**: Database caching + optimized queries (<4 seconds)  
✅ **JSON Response**: GeoJSON route + fuel stops + total cost  

**Vehicle Specifications** (per assignment):
- Maximum range: **500 miles** per tank
- Fuel efficiency: **10 miles per gallon**

---

## 🚀 Quick Start

### 1. Installation

cd C:\Users\Israe\fuel_route

# Install dependencies
poetry install

# Activate environment
poetry shell### 2. Environment Setup

# Copy environment template
copy .env.example .env

# Edit .env and add your MapQuest API key**Get FREE MapQuest API Key:**
1. Go to: https://developer.mapquest.com/
2. Sign up (free, 15,000 requests/month)
3. Go to "Keys & Reporting"
4. Copy your API key
5. Paste in `.env` file: `MAPQUEST_API_KEY=your_key_here`

### 3. Database Setup

cd src\fuel_route

# Run migrations
1. poetry run python manage.py makemigration
2. poetry run python manage.py migrate

# Create cache table
poetry run python manage.py createcachetable

### 4. Import Fuel Station Data

**Copy CSV file to project root first!**

# Import with complete data cleaning
poetry run python manage.py import_fuel_stations ..\..\fuel-prices-with-coordinates.csv


### 5. Run Server

poetry run python manage.py runserver at: **http://127.0.0.1:8000/**

---

## 📡 API Endpoints

### 1. Route Optimization (Main)

**POST** `/api/route/optimize/`

**Request:**
{
    "start": "New York, NY",
    "end": "Los Angeles, CA"
}**Example Response (Not Real Output):**
{
    "route_geometry": {
        "type": "LineString",
        "coordinates": [[-74.006, 40.7128], ..., [-118.243, 34.0522]]
    },
    "total_distance_miles": 2789.5,
    "total_fuel_cost": 967.23,
    "estimated_gallons": 278.9,
    "fuel_stops": [
        {
            "opis_id": 128,
            "name": "Pilot Travel Center",
            "city": "Denver",
            "state": "CO",
            "price": 3.45,
            "coordinates": [39.7392, -104.9903],
            "distance_from_start": 1025.3,
            "gallons_needed": 102.5,
            "cost_at_stop": 353.63
        }
    ],
    "stops_count": 6
}### 2. Health Check

**GET** `/api/health/`

{
    "status": "healthy"
}### 3. Statistics

**GET** `/api/stats/`

{
    "total_stations": 8153,
    "states_covered": 50,
    "cheapest_price": 2.85,
    "highest_price": 4.99
}---

## 🧪 Testing with Postman

1. Open Postman
2. Create POST request: `http://localhost:8000/api/route/optimize/`
3. Headers: `Content-Type: application/json`
4. Body (raw JSON):
{
    "start": "New York, NY",
    "end": "Los Angeles, CA"
}5. Send → Get response in <4 seconds!

**Visualize Route:**
1. Copy `route_geometry` from response
2. Go to https://geojson.io
3. Paste in left panel
4. See route on map!



## 👨‍💻 Author

Israe KHOUI  
israekhoui9@gmail.com / israekhoui10@gmail.com