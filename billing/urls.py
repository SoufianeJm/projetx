from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # Resource URLs
    path('resources/new/', views.ResourceCreateView.as_view(), name='resource_create'),
    path('resources/<int:pk>/edit/', views.ResourceUpdateView.as_view(), name='resource_update'),
    path('resources/<int:pk>/delete/', views.ResourceDeleteView.as_view(), name='resource_delete'),

    # Mission URLs
    path('missions/new/', views.MissionCreateView.as_view(), name='mission_create'),
    path('missions/<int:pk>/edit/', views.MissionUpdateView.as_view(), name='mission_update'),
    path('missions/<int:pk>/delete/', views.MissionDeleteView.as_view(), name='mission_delete'),

    path('facturation-slr/', views.facturation_slr_view, name='facturation_slr'),
] 