from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('approve/<int:loan_id>/', views.approve_loan, name='approve_loan'),
    path('loan/<int:loan_id>/reject/', views.reject_loan, name='reject_loan'),
    path('deposit/<int:member_id>/', views.deposit_savings, name='deposit_savings'),
    path('statement/<int:member_id>/', views.member_statement, name='member_statement'),
    path('arrears/', views.arrears_report, name='arrears_report'),
    path('loan/apply/<int:member_id>/', views.apply_loan, name='apply_loan'),
    path('loan/<int:pk>/', views.loan_detail, name='loan_detail'),
    path('loan/<int:loan_id>/pay/', views.receive_payment, name='receive_payment'),
    path('loan/<int:pk>/status/<str:action>/', views.update_loan_status, name='update_loan_status'),
    path('bulk-sms-reminder/', views.bulk_sms_reminder_view, name='bulk_sms_reminder'),
    path('withdraw/<int:member_id>/', views.withdraw_savings, name='withdraw_savings'),
    path('loans/all/', views.loan_list, name='loan_list'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # New Reports URLs
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/loan-portfolio/', views.loan_portfolio_report, name='loan_portfolio_report'),
    path('reports/savings/', views.savings_report, name='savings_report'),
    path('reports/cash-flow/', views.cash_flow_statement, name='cash_flow_statement'),
    path('reports/chart-of-accounts/', views.chart_of_accounts, name='chart_of_accounts'),
    path('reports/arrears/', views.arrears_report, name='arrears_report'),
    path('reports/portfolio-status/', views.portfolio_status_report, name='portfolio_status_report'),
    
]