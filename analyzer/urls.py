from django.urls import path

from . import views

app_name = 'analyzer'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload, name='upload'),
    path('output/', views.output, name='output'),
    path('example/', views.example, name='example')
]
