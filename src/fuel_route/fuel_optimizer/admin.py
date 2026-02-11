"""
Django Admin configuration for Fuel Optimizer
"""
from django.contrib import admin
from .models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    """Admin interface for managing fuel stations"""
    
    list_display = ['opis_id', 'name', 'city', 'state', 'retail_price', 'latitude', 'longitude']
    list_filter = ['state', 'city']
    search_fields = ['name', 'city', 'state', 'opis_id']
    ordering = ['retail_price']
    list_per_page = 50
    
    readonly_fields = ['created_at', 'updated_at']