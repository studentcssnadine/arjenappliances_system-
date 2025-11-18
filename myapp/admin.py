from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Customer, PaymentRecord, CustomerItem, 
    Transaction, MonthlyStatement, CustomerHistory, 
    UserPermission, UserActivityLog
)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'full_name', 'email', 'role', 'status', 'created_at')
    list_filter = ('role', 'status', 'is_active', 'created_at')
    search_fields = ('username', 'full_name', 'email')
    ordering = ('-created_at',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('full_name', 'phone', 'role', 'customer_id', 'status')
        }),
    )

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customers_name', 'contact', 'date_delivered', 'monthly', 'term', 'status', 'balance')
    list_filter = ('status', 'date_delivered', 'created_at')
    search_fields = ('customers_name', 'contact', 'address')
    ordering = ('-created_at',)
    readonly_fields = ('payments', 'balance', 'payment_count', 'next_due_date', 'is_overdue', 'overdue_amount')
    
    fieldsets = (
        ('Customer Information', {
            'fields': ('customers_name', 'address', 'contact')
        }),
        ('Contract Details', {
            'fields': ('item', 'date_delivered', 'amount', 'monthly', 'monthly_due', 'term', 'rebates', 'downpayment')
        }),
        ('Payment Status', {
            'fields': ('payments', 'status', 'completion_date')
        }),
        ('Calculated Fields', {
            'fields': ('balance', 'payment_count', 'next_due_date', 'is_overdue', 'overdue_amount'),
            'classes': ('collapse',)
        }),
    )

@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = ('payment_number', 'customer', 'payment_date', 'amount_paid', 'payment_method')
    list_filter = ('payment_date', 'payment_method', 'created_at')
    search_fields = ('customer__customers_name', 'transaction_number', 'notes')
    ordering = ('-payment_date', '-created_at')
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('customer', 'payment_number', 'payment_date', 'amount_paid', 'payment_method')
        }),
        ('Transaction Info', {
            'fields': ('transaction_number', 'reference_id', 'notes')
        }),
    )

@admin.register(CustomerItem)
class CustomerItemAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'item_model', 'customer', 'original_price', 'status', 'created_at')
    list_filter = ('status', 'good_as_cash', 'created_at')
    search_fields = ('item_name', 'item_model', 'customer__customers_name')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_number', 'customer', 'transaction_type', 'amount', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('transaction_number', 'customer__customers_name', 'description')

@admin.register(MonthlyStatement)
class MonthlyStatementAdmin(admin.ModelAdmin):
    list_display = ('customer', 'statement_date', 'due_date', 'amount_due', 'amount_paid', 'status')
    list_filter = ('status', 'statement_date', 'due_date')
    search_fields = ('customer__customers_name',)

@admin.register(CustomerHistory)
class CustomerHistoryAdmin(admin.ModelAdmin):
    list_display = ('customers_name', 'item_name', 'item_model', 'total_amount', 'total_payments', 'transaction_number', 'completed_by', 'term', 'final_status')
    list_filter = ('final_status', 'completion_date', 'archived_at')
    search_fields = ('customers_name', 'contact', 'item_name', 'transaction_number')

@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'permission_name', 'can_create', 'can_read', 'can_update', 'can_delete')
    list_filter = ('permission_name', 'can_create', 'can_read', 'can_update', 'can_delete')
    search_fields = ('user__username', 'permission_name')

@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'timestamp')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'action', 'description')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)
