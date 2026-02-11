"""
API Views for Fuel Route Optimizer
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RouteOptimizationRequestSerializer
from .services import RouteOptimizationService

logger = logging.getLogger('fuel_optimizer')


class RouteOptimizationView(APIView):
    """
    POST endpoint for route optimization with fuel stops.
    
    Endpoint: POST /api/route/optimize/
    
    Request:
        {
            "start": "New York, NY",
            "end": "Los Angeles, CA"
        }
    
    Response:
        {
            "route_geometry": {...},
            "total_distance_miles": 2789.5,
            "total_fuel_cost": 967.23,
            "estimated_gallons": 278.9,
            "fuel_stops": [...],
            "stops_count": 6
        }
    """

    def post(self, request):
        """Optimize route with fuel stops"""
        # Validate request
        serializer = RouteOptimizationRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.warning(f"Invalid request: {serializer.errors}")
            return Response(
                {
                    'error': 'Invalid request',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_location = serializer.validated_data['start']
            end_location = serializer.validated_data['end']
            
            # Optimize route
            service = RouteOptimizationService()
            result = service.optimize_route(start_location, end_location)
            
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            # Client errors (invalid locations, no route, etc.)
            logger.warning(f"Client error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            # Server errors
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Internal server error. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthCheckView(APIView):
    """Health check endpoint"""

    def get(self, request):
        """Simple health check"""
        return Response({'status': 'healthy'}, status=status.HTTP_200_OK)


class StatsView(APIView):
    """Statistics about fuel stations in database"""

    def get(self, request):
        """Get fuel station statistics"""
        from django.db.models import Count, Min, Max
        from .models import FuelStation

        total = FuelStation.objects.count()
        
        if total == 0:
            return Response({
                'total_stations': 0,
                'message': 'No fuel stations in database. Run: python manage.py import_fuel_stations'
            })
        
        states = FuelStation.objects.values('state').distinct().count()
        prices = FuelStation.objects.aggregate(
            min_price=Min('retail_price'),
            max_price=Max('retail_price')
        )

        return Response({
            'total_stations': total,
            'states_covered': states,
            'cheapest_price': float(prices['min_price']),
            'highest_price': float(prices['max_price'])
        }, status=status.HTTP_200_OK)