from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.index, name='index'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('contact/', views.contact_view, name='contact'),
    path('about/', views.about_view, name='about'),
    path('careers/', views.careers_view, name='careers'),
    path('careers/apply/', views.general_application_view,
         name='general_application'),
    path('news/', views.news_list_view, name='news_list'),
    path('news/<slug:slug>/', views.news_detail_view, name='news_detail'),
    path('careers/<int:pk>/', views.job_detail_view, name='job_detail'),
    path("order/", views.order_request_view, name="order"),
    path("order/<str:reference>/received/",
         views.order_success_view, name="order_success"),
    path('privacy/', views.privacy_view, name='privacy'),
    path('terms/', views.terms_view, name='terms')
]
