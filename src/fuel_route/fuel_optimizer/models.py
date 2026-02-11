"""
Fuel Station Model with optimized indexes for fast queries.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class FuelStation(models.Model):
    """
    Fuel station with geocoded coordinates and price information.
    Optimized with database indexes for fast spatial and price queries.
    """
    opis_id = models.IntegerField(
        unique=True, 
        db_index=True,
        help_text="Unique OPIS Truckstop ID"
    )
    name = models.CharField(max_length=200, help_text="Station name")
    address = models.CharField(max_length=300, blank=True, help_text="Street address")
    city = models.CharField(max_length=100, db_index=True, help_text="City name")
    state = models.CharField(max_length=2, db_index=True, help_text="State code (e.g., CA, NY)")
    
    retail_price = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        db_index=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Retail fuel price per gallon (USD)"
    )
    
    # Geocoded coordinates (high precision with Decimal)
    latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7,
        help_text="Latitude coordinate"
    )
    longitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7,
        help_text="Longitude coordinate"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fuel_stations'
        indexes = [
            models.Index(fields=['latitude', 'longitude'], name='lat_lon_idx'),
            models.Index(fields=['retail_price'], name='price_idx'),
            models.Index(fields=['state', 'city'], name='location_idx'),
        ]
        ordering = ['retail_price']  # Default: cheapest first

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state} (${self.retail_price}/gal)"

    @property
    def coordinates(self):
        """Return coordinates as (latitude, longitude) tuple"""
        return (float(self.latitude), float(self.longitude))
    
    @property
    def location_display(self):
        """Return formatted location string"""
        return f"{self.city}, {self.state}"