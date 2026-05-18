from django.urls import path

from . import views

app_name = "credentials"

urlpatterns = [
    path("", views.credentials_list, name="list"),
    path("<str:platform>/", views.credential_edit, name="edit"),
    path("<str:platform>/disable/", views.credential_disable, name="disable"),
]
