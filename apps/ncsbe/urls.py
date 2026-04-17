from django.urls import path

from apps.ncsbe import views

urlpatterns = [
    path("", views.home, name="home"),
    path("county/<str:county_name>/", views.county_registrations, name="county_registrations"),
    path("voter/<str:ncid>/", views.voter_history, name="voter_history"),
]
