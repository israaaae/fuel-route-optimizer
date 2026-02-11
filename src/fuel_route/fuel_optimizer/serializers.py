"""
Serializers for API request/response validation
"""
from rest_framework import serializers
from django.core.validators import RegexValidator


class RouteOptimizationRequestSerializer(serializers.Serializer):
    """
    Request serializer with strict validation.
    """
    start = serializers.CharField(
        max_length=200,
        required=True,
        help_text="Starting location within USA (e.g., 'New York, NY')",
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z0-9\s,.-]+$",
                message="Location must contain only letters, numbers, spaces, commas, periods, and hyphens"
            )
        ],
        error_messages={
            'required': 'Start location is required',
            'blank': 'Start location cannot be empty',
        }
    )
    
    end = serializers.CharField(
        max_length=200,
        required=True,
        help_text="Destination location within USA (e.g., 'Los Angeles, CA')",
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z0-9\s,.-]+$",
                message="Location must contain only letters, numbers, spaces, commas, periods, and hyphens"
            )
        ],
        error_messages={
            'required': 'End location is required',
            'blank': 'End location cannot be empty',
        }
    )

    def validate(self, data):
        """Cross-field validation"""
        start = data.get('start', '').strip().lower()
        end = data.get('end', '').strip().lower()
        
        if start == end:
            raise serializers.ValidationError(
                "Start and end locations must be different"
            )
        
        return data


class FuelStopSerializer(serializers.Serializer):
    """Individual fuel stop information"""
    opis_id = serializers.IntegerField()
    name = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    price = serializers.FloatField()
    coordinates = serializers.ListField(child=serializers.FloatField())
    distance_from_start = serializers.FloatField()
    gallons_needed = serializers.FloatField()
    cost_at_stop = serializers.FloatField()


class RouteOptimizationResponseSerializer(serializers.Serializer):
    """Response format for route optimization"""
    route_geometry = serializers.DictField()
    total_distance_miles = serializers.FloatField()
    total_fuel_cost = serializers.FloatField()
    estimated_gallons = serializers.FloatField()
    fuel_stops = FuelStopSerializer(many=True)
    stops_count = serializers.IntegerField()