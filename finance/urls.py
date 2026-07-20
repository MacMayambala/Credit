from django.urls import path
from . import views
from django.urls import path
from .views import view_receipt
from .views import ExecutiveCEODashboardView, InterestIncomeReportView, LoansInArrearsReportView, TreasuryDashboardView, export_report_excel
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('approve/<int:pk>/', views.approve_loan, {'action': 'approve'}, name='approve_loan'),
    path('loan/<int:pk>/reject/', views.approve_loan, {'action': 'reject'}, name='reject_loan'),
    path('deposit/<int:member_id>/', views.deposit_savings, name='deposit_savings'),
    path('statement/<int:member_id>/', views.member_statement, name='member_statement'),
    path('arrears/', views.arrears_report, name='arrefars_report'),
    path('loan/apply/<int:member_id>/', views.apply_loan, name='apply_loan'),
    path('loan/<int:pk>/', views.loan_detail, name='loan_detail'),
    path('loan/<int:loan_id>/pay/', views.receive_payment, name='receive_payment'),
    #path('loan/<int:pk>/status/<str:action>/', views.update_loan_status, name='update_loan_status'),
    path('bulk-sms-reminder/', views.bulk_sms_reminder_view, name='bulk_sms_reminder'),
    path('withdraw/<int:member_id>/', views.withdraw_savings, name='withdraw_savings'),
    path('loans/all/', views.loan_list, name='loan_list'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # New Reports URLs
    # path('reports/', views.reports_dashboard, name='reports_dashboard'),
    # path('reports/loan-portfolio/', views.loan_portfolio_report, name='loan_portfolio_report'),
    path('reports/savings/', views.savings_report, name='savings_report'),
    path('reports/cash-flow/', views.cash_flow_statement, name='cash_flow_statement'),
    path('reports/chart-of-accounts/', views.chart_of_accounts, name='chart_of_accounts'),
    path('reports/arrears/', views.arrears_report, name='arreards_report'),
    path('reports/portfolio-status/', views.portfolio_status_report, name='portfolio_status_report'),
    path('transaction/<int:transaction_id>/reverse/', views.reverse_transaction, name='reverse_transaction'),
    path('loann/<int:loan_id>/', views.loan_details, name='loan_details'),

    ################################# Accounting API Endpoints #################################
    path('ledger/', views.general_ledger, name='general_ledger'),
    path('coa/', views.chart_of_accounts, name='chart_of_accounts'),
    path('expense/add/', views.record_expense, name='record_expense'),
    path('coa/edit/<int:pk>/', views.edit_chart_of_account, name='edit_coa'),
    path('coa/add/', views.create_chart_of_account, name='create_coa'),
    path('finance/', views.accounting_dashboard, name='finance_dashboard'),
    path('expense/add/', views.record_expense, name='record_expense'),
    path('ledger/inflow/', views.record_inflow, name='record_inflow'),
    path('accounts/hub/', views.accounts_hub, name='accounts_hub'),
    path('auto-repayment-dashboard/', views.auto_repayment_dashboard, name='auto_repayment_dashboard'),


    ###############################################################################################################
    
    path('dashboard/ceo/', ExecutiveCEODashboardView.as_view(), name='ceo_dashboard'),
    path('analytics/interest-income/', InterestIncomeReportView.as_view(), name='interest_report'),
    path('treasury/liquidity/', TreasuryDashboardView.as_view(), name='treasury_dashboard'),
    #path('system/export/', ExportFinancialReportView.as_view(), name='stream_export'),
    path('analytics/interest-income/', InterestIncomeReportView.as_view(), name='interest_income_report'),
    
    # 2. Distinct Export Endpoint
    #path('analytics/interest-income/export/', ExportFinancialReportView.as_view(), name='export_financial_report'),
    path('analytics/interest-income/', InterestIncomeReportView.as_view(), name='interest_income_report'),

    path('loan/<int:loan_id>/apply-penalty/', views.apply_manual_penalty, name='apply_manual_penalty'),
    path('penalty/<int:penalty_id>/waive/', views.waive_manual_penalty, name='waive_manual_penalty'),
    path('waive-auto-penalty/<int:installment_id>/', views.waive_auto_penalty, name='waive_auto_penalty'),
    path('analytics/arrears-delinquency/', LoansInArrearsReportView.as_view(), name='arrears_report'),
    path('receipt/', view_receipt, name='view_receipt'),
     # ========================
    # REPORTS
    # ========================
    path('report/', views.report_view, name='report_view'),
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/loan/', views.loan_report, name='loan_report'),
    path('reports/member/', views.member_report, name='member_report'),
    path('reports/savings/', views.savings_report, name='savings_report'),
    path('reports/financial/', views.financial_report, name='financial_report'),
    path('reports/officer/', views.officer_report, name='officer_report'),
    path('reports/accounting/', views.accounting_report, name='accounting_report'),
    path('reports/audit/', views.audit_report, name='audit_report'),
    path('reports/inventory/', views.inventory_report, name='inventory_report'),
    path('reports/interest/', views.interest_report, name='interest_report'),
    path('reports/loan-portfolios/', views.loan_portfolio_report, name='loan_portfolio_report'),
    path('reports/portfolio-status/', views.portfolio_status_report, name='portfolio_status_report'),
    path('reports/arrears/', views.arrears_report, name='arrears_report'),
    path('export/excel/', export_report_excel, name='export_report_excel'),
    path('reports/general-ledger/', views.general_ledger_report, name='general_ledger_report'),
    path('reports/loan-portfolio/', views.loan_portfolio_report, name='loan_portfolio_report'),
    

    
]