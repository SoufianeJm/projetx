from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('resources/', views.resource_list_view, name='resource_list'),
    path('resources/create/', views.resource_create, name='resource_create'),
    path('resources/<int:pk>/update/', views.resource_update, name='resource_update'),
    path('resources/<int:pk>/delete/', views.resource_delete, name='resource_delete'),
    path('missions/', views.mission_list_view, name='mission_list'),
    path('missions/create/', views.mission_create, name='mission_create'),
    path('missions/<int:pk>/update/', views.mission_update, name='mission_update'),
    path('missions/<int:pk>/delete/', views.mission_delete, name='mission_delete'),
    path('missions/tracking/', views.mission_calculation_tracking_view, name='mission_calculation_tracking'),
    path('facturation/slr/', views.facturation_slr, name='facturation_slr'),
] 