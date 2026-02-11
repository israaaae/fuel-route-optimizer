"""
URL patterns for Fuel Optimizer API
"""
from django.urls import path

from .views import HealthCheckView, RouteOptimizationView, StatsView

app_name = 'fuel_optimizer'

urlpatterns = [
    path('route/optimize/', RouteOptimizationView.as_view(), name='optimize_route'),
    path('health/', HealthCheckView.as_view(), name='health_check'),
    path('stats/', StatsView.as_view(), name='stats'),
]