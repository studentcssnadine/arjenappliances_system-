from django.urls import path
from . import views

urlpatterns = [
    # Landing page
    path('', views.index, name='index'),
    path('account/profile/', views.edit_profile, name='edit_profile'),
    path('account/profile/data/', views.get_profile_data, name='get_profile_data'),
    # Profile update endpoints
    path('account/update/customer/', views.customer_update_profile, name='customer_update_profile'),
    path('account/update/staff/', views.staff_update_profile, name='staff_update_profile'),
    path('account/update/admin/', views.admin_update_profile, name='admin_update_profile'),
    
    # Authentication
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.register, name='register'),
    
    
    # Dashboards
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('staff-dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('customer-dashboard/', views.customer_dashboard, name='customer_dashboard'),
    
    # Customer Management
    path('customers/', views.customers_list, name='customers_list'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/edit/', views.edit_customer, name='edit_customer'),
    path('customers/<int:customer_id>/remove/', views.remove_customer, name='remove_customer'),
    path('customers/<int:customer_id>/payments/', views.customer_payments, name='customer_payments'),
    
    # Customer Portal Navigation
    path('customer/transactions/', views.customer_transactions, name='customer_transactions'),
    path('customer/items/', views.customer_items, name='customer_items'),
    path('customer/statements/', views.monthly_statements, name='monthly_statements'),
    path('customer/profile/update/', views.customer_update_profile, name='customer_update_profile'),
    path('staff/profile/update/', views.staff_update_profile, name='staff_update_profile'),
    path('admin/profile/update/', views.admin_update_profile, name='admin_update_profile'),
    
    # Modal endpoints (AJAX)
    path('modal/add-item-content/', views.add_item_modal_content, name='add_item_modal_content'),
    path('modal/edit-item-content/<int:item_id>/', views.edit_item_modal_content, name='edit_item_modal_content'),
    
    # Payment Management
    path('payments/', views.payments, name='payments'),
    path('payments/record/', views.record_payment, name='record_payment'),
    
    # API endpoints
    path('api/customer-items/<int:customer_id>/', views.get_customer_items, name='get_customer_items'),
    
    # Reports
    path('reports/due-payments/', views.due_payments_report, name='due_payments_report'),
    path('reports/customer-history/', views.customer_history, name='customer_history'),
    path('reports/', views.reports, name='reports'),
    
    # User Management (Admin only)
    path('users/manage/', views.manage_users, name='manage_users'),
    path('run-migrations/', views.run_migrations_view, name='run_migrations'),
   
]
