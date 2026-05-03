from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_member, name='register_member'),
    path('profile/<int:member_id>/', views.member_profile, name='member_profile'),
    path('customers/', views.customer_list, name='customer_list'),
    path('members/update-kyc/<int:member_id>/', views.update_kyc, name='update_kyc'), # Add this line
    path('member/<int:member_id>/edit/', views.edit_member, name='edit_member'),
    path('auth/login/', views.CustomLoginView.as_view(), name='login'),
    path('auth/logout/', views.custom_logout, name='logout'),

]