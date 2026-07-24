from django.urls import path, re_path
from . import views

app_name = "hardware"

urlpatterns = [
    # POS & Dashboard
    path('pos/', views.POSView.as_view(), name='pos'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('checkout/', views.pos_checkout_view, name='pos_checkout'),
    re_path(r'^receipt/(?P<sale_id>[0-9a-f-]+)/$', views.receipt_view, name='receipt'),
    path('sales/', views.SalesListView.as_view(), name='sales_list'),
    path("process-sale/", views.secure_process_sale, name="process_sale"),
    
    # Products - UUID
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/add/', views.ProductCreateView.as_view(), name='product_add'),
    path('products/<uuid:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('products/<uuid:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    
    # Categories - UUID
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category_add'),
    path('categories/<uuid:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<uuid:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    
    # Suppliers - Integer IDs (not UUID)
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/add/', views.SupplierCreateView.as_view(), name='supplier_add'),
    path('suppliers/<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='supplier_delete'),
    
    # Purchases
    path('purchases/', views.PurchaseListView.as_view(), name='purchase_list'),
    path('purchases/add/', views.PurchaseCreateView.as_view(), name='purchase_add'),
    path('purchases/<uuid:pk>/edit/', views.PurchaseUpdateView.as_view(), name='purchase_edit'),
    path('purchases/<uuid:pk>/delete/', views.PurchaseDeleteView.as_view(), name='purchase_delete'),
    
    # Reports
    path('reports/', views.ReportListView.as_view(), name='reports'),
    path('reports/journal/', views.GeneralLedgerReportView.as_view(), name='journal_report'),
    path('reports/general-ledger/', views.GeneralLedgerReportView.as_view(), name='general_ledger_report'),
    path('reports/trial-balance/', views.TrialBalanceReportView.as_view(), name='trial_balance_report'),
    path('reports/sales/', views.SalesReportView.as_view(), name='sales_report'),
    path('reports/till-sheet/', views.TillSheetReportView.as_view(), name='till_sheet_report'),
    path('reports/audit-trail/', views.AuditTrailReportView.as_view(), name='audit_trail_report'),
    path('reports/export/', views.export_report_csv, name='export_report'),
    path('transactions/', views.TransactionListView.as_view(), name='transactions_report'),
    path('transactions/<int:pk>/', views.TransactionDetailView.as_view(), name='transaction_detail'),
]