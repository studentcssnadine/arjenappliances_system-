#!/usr/bin/env python
import os
import sys
import django
from datetime import date
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import Customer, PaymentRecord, CustomUser

def fix_payment_issue():
    print("=== DIAGNOSING PAYMENT RECORDING ISSUE ===\n")
    
    # Get test data
    customer = Customer.objects.filter(status='active').first()
    user = CustomUser.objects.filter(is_active=True).first()
    
    if not customer or not user:
        print("❌ Missing test data")
        return
    
    print(f"Testing with customer: {customer.customers_name}")
    print(f"Testing with user: {user.username}")
    
    # Try to create a payment with minimal data
    try:
        print("\n=== ATTEMPTING PAYMENT CREATION ===")
        
        # Method 1: Try with all fields explicitly set
        payment_data = {
            'customer': customer,
            'payment_date': date.today(),
            'amount_paid': Decimal('100.00'),
            'payment_method': 'Cash',
            'recorded_by': user,
            'has_rebate': False,
            'rebate_amount': Decimal('0.00'),
            'notes': 'Test payment to diagnose issue'
        }
        
        print("Creating payment with explicit data...")
        payment = PaymentRecord(**payment_data)
        
        # Try to save
        print("Attempting to save...")
        payment.save()
        
        print(f"✅ SUCCESS! Payment created with ID: {payment.id}")
        print(f"   Transaction Number: {payment.transaction_number}")
        print(f"   Payment Number: {payment.payment_number}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        
        # Try to identify the specific issue
        error_str = str(e).lower()
        if 'not null constraint' in error_str:
            print("   → Issue: NOT NULL constraint violation")
            if 'payment_number' in error_str:
                print("   → Field: payment_number")
            elif 'transaction_number' in error_str:
                print("   → Field: transaction_number")
        elif 'unique constraint' in error_str:
            print("   → Issue: UNIQUE constraint violation")
        elif 'foreign key' in error_str:
            print("   → Issue: Foreign key constraint")
        
        import traceback
        print(f"\nFull traceback:\n{traceback.format_exc()}")
        
        return False

def check_database_schema():
    print("\n=== CHECKING DATABASE SCHEMA ===")
    
    from django.db import connection
    cursor = connection.cursor()
    
    # Check PaymentRecord table structure
    cursor.execute("PRAGMA table_info(myapp_paymentrecord)")
    columns = cursor.fetchall()
    
    print("PaymentRecord table columns:")
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        not_null = col[3]
        default_val = col[4]
        print(f"  - {col_name}: {col_type} (NOT NULL: {bool(not_null)}, DEFAULT: {default_val})")
        
        # Check problematic fields
        if col_name in ['payment_number', 'transaction_number'] and not_null:
            print(f"    ⚠️  WARNING: {col_name} is NOT NULL - this might cause issues!")

if __name__ == "__main__":
    check_database_schema()
    success = fix_payment_issue()
    
    if success:
        print("\n🎉 PAYMENT CREATION WORKS!")
    else:
        print("\n💥 PAYMENT CREATION FAILED!")
        print("\nSuggested fixes:")
        print("1. Run database migrations")
        print("2. Check field constraints")
        print("3. Verify model save method")
