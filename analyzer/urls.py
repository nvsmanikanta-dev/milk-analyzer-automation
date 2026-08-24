from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/analyzer-connect/", views.analyzer_connect, name="analyzer_connect"),
    path("api/analyzer-start/", views.analyzer_start, name="analyzer_start"),
    path("api/analyzer-stop/", views.analyzer_stop, name="analyzer_stop"),
    path("api/analyzer-status/", views.analyzer_status, name="analyzer_status"),
    path("api/validate-sample/", views.validate_sample, name="validate_sample"),
    path("records/", views.records, name="records"),
    path("summary/", views.summary, name="summary"),
    path("server-sync/", views.server_sync, name="server_sync"),
    path("api/server-status/", views.server_status, name="server_status"),
]
