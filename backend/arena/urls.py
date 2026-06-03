from django.urls import path

from . import views

urlpatterns = [
    path("arena/state/", views.ArenaStateView.as_view(), name="arena-state"),
    path("arena/tips/toggle/", views.ToggleTipView.as_view(), name="arena-toggle"),
    path(
        "arena/sync/",
        views.TriggerSpreadsheetSyncView.as_view(),
        name="arena-sync",
    ),
    path("auth/csrf/", views.csrf_view, name="auth-csrf"),
    path("auth/whoami/", views.WhoAmIView.as_view(), name="auth-whoami"),
]
