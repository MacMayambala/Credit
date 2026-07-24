from django.urls import path
from . import views
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import TemplateDownloadView, MigrationPreviewView, MigrationImportExecutionView

urlpatterns = [
    path('register/', views.register_member, name='register_member'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/<int:member_id>/', views.member_profile, name='member_profile'),
    path('customers/', views.customer_list, name='customer_list'),
    path('members/update-kyc/<int:member_id>/', views.update_kyc, name='update_kyc'), # Add this line
    path('member/<int:member_id>/edit/', views.edit_member, name='edit_member'),
    path('auth/login/', views.user_login, name='login'),
    path('auth/logout/', views.custom_logout, name='logout'),
    # 1. Page to request a password reset (Enter Email)
   # project/urls.py


    # urls.py
    # 1. Request Link
    path('password_reset/', 
         views.MyPasswordResetView.as_view(), 
         name='password_reset'),
    
    # 2. Email Sent Success Page
    path('password_reset/done/', 
         views.MyPasswordResetDoneView.as_view(), 
         name='password_reset_done'),
    
    # 3. The link from the email
    path('reset/<uidb64>/<token>/', 
         views.MyPasswordResetConfirmView.as_view(), 
         name='password_reset_confirm'),
    
    # 4. Final Success Page
    path('reset/done/', 
         views.MyPasswordResetCompleteView.as_view(), 
         name='password_reset_complete'),



    path('staff/', views.UserListView.as_view(), name='user_list'),
    path('staff/add/', views.UserCreateView.as_view(), name='user_create'),
    path('staff/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('staff/<int:user_id>/toggle/', views.toggle_user_status, name='toggle_user_status'),

     path(
        'select-2fa/',
        views.Select2FAMethodView.as_view(),
        name='select_2fa_method'
    ),

    path(
        'verify-2fa/',
        views.Verify2FAView.as_view(),
        name='verify_2fa'
    ),
    path('setup-authenticator/', views.setup_authenticator, name='setup_authenticator'),
    path('management/rights/', views.manage_user_rights, name='manage_user_rights'),
    path('management/group-rights/', views.manage_group_permissions, name='manage_group_permissions'),
    path('management/group-rights/<int:group_id>/', views.manage_group_permissions, name='manage_group_permissions_detail'),
    path('template/download/', TemplateDownloadView.as_view(), name='template_download'),
    path('import/preview/', MigrationPreviewView.as_view(), name='import_preview'),
    path('import/execute/', MigrationImportExecutionView.as_view(), name='import_execute'),
    path('import/dashboard/', views.MigrationDashboardView.as_view(), name='import_dashboard'),
    
]
