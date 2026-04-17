from django.urls import path

from . import views

app_name = "demo"

urlpatterns = [
    path("", views.DemoView.as_view(), name="index"),
]
