# myapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('file_upload/', views.file_upload_view, name='file-upload-view'),
    # ... other app-specific patterns
]
