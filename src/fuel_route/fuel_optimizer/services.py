"""
Route Optimization Service with MapQuest API (1 call only).
Hybrid algorithm combining bounding box filtering and deviation scoring.
"""
import hashlib
import logging
from typing import Dict, List, Tuple, Optional

import requests
from django.conf import settings
from django.core.cache import cache
from geopy.distance import geodesic

from .models import FuelStation

logger = logging.getLogger('fuel_optimizer')


class RouteOptimizationService:
    """
    Service for optimizing routes with cost-effective fuel stops.
    
    Features:
    - Single API call to MapQuest (geocoding + routing)
    - Intelligent fuel stop selection (price + deviation scoring)
    - Caching for improved performance
    - 500-mile range, 10 MPG calculations
    """

    def __init__(self):
        self.api_key = settings.MAPQUEST_API_KEY
        self.base_url = settings.MAPQUEST_BASE_URL
        self.vehicle_range = settings.VEHICLE_RANGE_MILES
        self.vehicle_mpg = settings.VEHICLE_MPG

    def optimize_route(self, start_location: str, end_location: str) -> Dict:
        """
        Main optimization method.
        
        Args:
            start_location: Start address (e.g., "New York, NY")
            end_location: End address (e.g., "Los Angeles, CA")
            
        Returns:
            Dict with route_geometry, fuel_stops, total_cost, etc.
        """
        logger.info(f"Optimizing route: {start_location} -> {end_location}")
        
        try:
            # Step 1: Get route with geocoding (SINGLE API CALL)
            route_data = self._get_route_with_geocoding(start_location, end_location)
            
            # Step 2: Find optimal fuel stops
            fuel_stops = self._find_optimal_fuel_stops(
                route_data['start_coords'],
                route_data['end_coords'],
                route_data['coordinates'],
                route_data['distance_miles']
            )
            
            # Step 3: Calculate costs
            result = self._calculate_costs(
                route_data,
                fuel_stops
            )
            
            logger.info(
                f"Route optimized: {len(fuel_stops)} stops, "
                f"${result['total_fuel_cost']:.2f} total cost"
            )
            
            return result

        except Exception as e:
            logger.error(f"Route optimization failed: {e}")
            raise

    def _get_route_with_geocoding(self, start: str, end: str) -> Dict:
        """
        Get route using MapQuest API.
        This does geocoding + routing in ONE SINGLE API CALL.
        
        Returns:
            Dict with distance_miles, coordinates, start_coords, end_coords
        """
        # Check cache first
        cache_key = f"route_{hashlib.md5(f'{start}:{end}'.encode()).hexdigest()}"
        cached_route = cache.get(cache_key)
        
        if cached_route:
            logger.info(f"Cache hit for route: {start} -> {end}")
            return cached_route

        if not self.api_key:
            raise ValueError(
                "MAPQUEST_API_KEY not set. Get a free key at: "
                "https://developer.mapquest.com/"
            )

        try:
            # ONE SINGLE API CALL (geocoding + routing)
            logger.info(f"Calling MapQuest API: {start} -> {end}")
            
            response = requests.get(
                self.base_url,
                params={
                    'key': self.api_key,
                    'from': start,           # MapQuest geocodes automatically
                    'to': end,               # MapQuest geocodes automatically
                    'unit': 'm',             # Miles
                    'routeType': 'fastest',
                    'fullShape': 'true',     # Get all coordinates
                    'shapeFormat': 'raw',    # Raw coordinates (not encoded)
                },
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            if data['info']['statuscode'] != 0:
                error_messages = data['info'].get('messages', ['Unknown error'])
                raise ValueError(f"MapQuest API error: {', '.join(error_messages)}")
            
            route = data['route']
            
            # Extract route data
            distance_miles = route['distance']  # Already in miles
            
            # Convert shape points to GeoJSON format
            shape_points = route['shape']['shapePoints']
            coordinates = [
                [shape_points[i+1], shape_points[i]]  # [lon, lat] for GeoJSON
                for i in range(0, len(shape_points), 2)
            ]
            
            # Extract start/end coordinates
            start_loc = route['locations'][0]['latLng']
            end_loc = route['locations'][1]['latLng']
            
            route_data = {
                'distance_miles': distance_miles,
                'coordinates': coordinates,
                'start_coords': (start_loc['lat'], start_loc['lng']),
                'end_coords': (end_loc['lat'], end_loc['lng']),
            }
            
            # Cache for 1 hour
            cache.set(cache_key, route_data, settings.ROUTE_CACHE_TIMEOUT)
            
            return route_data

        except requests.exceptions.RequestException as e:
            logger.error(f"MapQuest API error: {e}")
            raise ValueError(f"Routing service error: {str(e)}")
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected API response format: {e}")
            raise ValueError("Invalid response from routing service")

    def _find_optimal_fuel_stops(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float],
        route_coordinates: List[List[float]],
        total_distance: float
    ) -> List[Dict]:
        """
        Find optimal fuel stops using hybrid algorithm.
        
        Combines:
        - Bounding box filtering (Project 2 - fast)
        - Deviation scoring (Project 1 - intelligent)
        
        Algorithm:
        1. Check if fuel stops needed (distance > 500 miles)
        2. Filter stations within route bounding box
        3. Sample route points every 50 miles
        4. When fuel < 25% tank, search nearby stations
        5. Score stations: price + (route_deviation * 0.1)
        6. Select best station (lowest score)
        """
        # No stops needed for short trips
        if total_distance <= self.vehicle_range:
            logger.info(f"Short trip ({total_distance:.1f} miles), no fuel stops needed")
            return []

        # Bounding box filtering (Project 2 optimization)
        min_lon = min(coord[0] for coord in route_coordinates)
        max_lon = max(coord[0] for coord in route_coordinates)
        min_lat = min(coord[1] for coord in route_coordinates)
        max_lat = max(coord[1] for coord in route_coordinates)
        
        # Add margin (0.5 degrees ≈ 35 miles)
        margin = 0.5
        
        stations = FuelStation.objects.filter(
            latitude__gte=min_lat - margin,
            latitude__lte=max_lat + margin,
            longitude__gte=min_lon - margin,
            longitude__lte=max_lon + margin
        ).order_by('retail_price')
        
        if not stations.exists():
            logger.warning("No fuel stations found in route area")
            return []
        
        logger.info(f"Found {stations.count()} stations in route area")
        
        # Initialize tracking variables
        fuel_stops = []
        remaining_range = self.vehicle_range
        last_stop_coords = start_coords
        
        # Sample points every 50 miles (Project 1 approach)
        sample_interval = max(1, len(route_coordinates) // int(total_distance / 50))
        sampled_points = route_coordinates[::sample_interval]
        
        for i, point in enumerate(sampled_points):
            # Calculate progress along route
            progress = (i / len(sampled_points)) * total_distance
            
            # Check if we need fuel (< 25% of tank range remaining)
            if remaining_range < (self.vehicle_range * 0.25) and progress < total_distance:
                logger.debug(f"Low fuel at {progress:.1f} miles, searching for station...")
                
                # Find nearby stations
                nearby_stations = []
                search_radius = self.vehicle_range * 0.2  # 20% of range = 100 miles
                
                point_coords = (point[1], point[0])  # Convert to (lat, lon)
                
                for station in stations:
                    distance_to_station = self._calculate_distance(
                        point_coords, 
                        station.coordinates
                    )
                    
                    if distance_to_station <= search_radius:
                        # Calculate deviation (Project 1 intelligence)
                        deviation = self._calculate_deviation(
                            point_coords,
                            station.coordinates,
                            end_coords
                        )
                        
                        # Score: price + deviation penalty
                        score = float(station.retail_price) + (deviation * 0.1)
                        
                        nearby_stations.append({
                            'station': station,
                            'distance': distance_to_station,
                            'deviation': deviation,
                            'score': score
                        })
                
                # Select best station (lowest score)
                if nearby_stations:
                    best = min(nearby_stations, key=lambda x: x['score'])
                    station = best['station']
                    
                    # Calculate fuel needed since last stop
                    distance_since_last = self._calculate_distance(
                        last_stop_coords,
                        station.coordinates
                    )
                    gallons_needed = distance_since_last / self.vehicle_mpg
                    
                    fuel_stops.append({
                        'opis_id': station.opis_id,
                        'name': station.name,
                        'city': station.city,
                        'state': station.state,
                        'price': float(station.retail_price),
                        'coordinates': list(station.coordinates),
                        'distance_from_start': progress,
                        'gallons_needed': round(gallons_needed, 2),
                        'cost_at_stop': round(gallons_needed * float(station.retail_price), 2)
                    })
                    
                    logger.info(
                        f"Fuel stop #{len(fuel_stops)}: {station.name} "
                        f"({station.city}, {station.state}) - "
                        f"${station.retail_price}/gal"
                    )
                    
                    # Update tracking
                    last_stop_coords = station.coordinates
                    remaining_range = self.vehicle_range
            
            # Update remaining range
            if i > 0:
                distance_covered = self._calculate_distance(
                    (sampled_points[i-1][1], sampled_points[i-1][0]),
                    (point[1], point[0])
                )
                remaining_range -= distance_covered
        
        return fuel_stops

    def _calculate_distance(
        self, 
        point1: Tuple[float, float], 
        point2: Tuple[float, float]
    ) -> float:
        """
        Calculate distance between two points using geodesic.
        Includes caching for performance.
        """
        cache_key = f"dist_{point1[0]:.4f}_{point1[1]:.4f}_{point2[0]:.4f}_{point2[1]:.4f}"
        cached_distance = cache.get(cache_key)
        
        if cached_distance is not None:
            return cached_distance
        
        distance = geodesic(point1, point2).miles
        
        # Cache for 24 hours
        cache.set(cache_key, distance, 86400)
        
        return distance

    def _calculate_deviation(
        self,
        current_point: Tuple[float, float],
        station_coords: Tuple[float, float],
        end_coords: Tuple[float, float]
    ) -> float:
        """
        Calculate route deviation (detour distance).
        
        Formula:
        Deviation = (distance_to_station + distance_station_to_end) - direct_distance_to_end
        
        Lower deviation = station is closer to direct route
        """
        dist_to_station = self._calculate_distance(current_point, station_coords)
        dist_station_to_end = self._calculate_distance(station_coords, end_coords)
        direct_to_end = self._calculate_distance(current_point, end_coords)
        
        deviation = (dist_to_station + dist_station_to_end) - direct_to_end
        
        return max(0, deviation)  # Deviation can't be negative

    def _calculate_costs(
        self,
        route_data: Dict,
        fuel_stops: List[Dict]
    ) -> Dict:
        """
        Calculate trip costs and format final response.
        """
        distance_miles = route_data['distance_miles']
        total_gallons = distance_miles / self.vehicle_mpg
        
        # Calculate total fuel cost
        if not fuel_stops:
            total_cost = 0.0
        else:
            total_cost = sum(stop['cost_at_stop'] for stop in fuel_stops)

        # Build GeoJSON geometry
        geometry = {
            'type': 'LineString',
            'coordinates': route_data['coordinates']
        }

        return {
            'route_geometry': geometry,
            'total_distance_miles': round(distance_miles, 1),
            'total_fuel_cost': round(total_cost, 2),
            'estimated_gallons': round(total_gallons, 1),
            'fuel_stops': fuel_stops,
            'stops_count': len(fuel_stops),
        }