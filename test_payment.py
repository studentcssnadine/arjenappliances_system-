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

def test_payment_system():
    print("=== TESTING PAYMENT RECORDING SYSTEM ===\n")
    
    # Check if there are customers
    customers = Customer.objects.filter(status='active')
    print(f"1. Active customers found: {customers.count()}")
    
    if customers.count() == 0:
        print("❌ No active customers found. Cannot test payment recording.")
        return False
    
    # Get first customer for testing
    test_customer = customers.first()
    print(f"2. Testing with customer: {test_customer.customers_name}")
    
    # Check if there are users (for recorded_by)
    users = CustomUser.objects.filter(is_active=True)
    print(f"3. Active users found: {users.count()}")
    
    if users.count() == 0:
        print("❌ No active users found. Cannot test payment recording.")
        return False
    
    test_user = users.first()
    print(f"4. Testing with user: {test_user.username}")
    
    # Get initial payment count
    initial_payment_count = PaymentRecord.objects.count()
    initial_customer_payments = test_customer.payments
    print(f"5. Initial payment records: {initial_payment_count}")
    print(f"6. Customer's current total payments: ₱{initial_customer_payments}")
    
    # Test payment creation
    try:
        print("\n=== CREATING TEST PAYMENT ===")
        test_payment = PaymentRecord.objects.create(
            customer=test_customer,
            payment_date=date.today(),
            amount_paid=Decimal('1500.00'),
            payment_method='Cash',
            recorded_by=test_user,
            has_rebate=True,
            rebate_amount=Decimal('100.00'),
            notes='Test payment from automated test'
        )
        
        print(f"✅ Payment created successfully!")
        print(f"   - Payment ID: {test_payment.id}")
        print(f"   - Payment Number: {test_payment.payment_number}")
        print(f"   - Transaction Number: {test_payment.transaction_number}")
        print(f"   - Amount: ₱{test_payment.amount_paid}")
        print(f"   - Rebate: ₱{test_payment.rebate_amount}")
        
        # Check if customer payments were updated
        test_customer.refresh_from_db()
        new_customer_payments = test_customer.payments
        print(f"   - Customer payments updated: ₱{initial_customer_payments} → ₱{new_customer_payments}")
        
        # Verify payment count increased
        final_payment_count = PaymentRecord.objects.count()
        print(f"   - Payment records: {initial_payment_count} → {final_payment_count}")
        
        if final_payment_count == initial_payment_count + 1:
            print("✅ Payment count increased correctly")
        else:
            print("❌ Payment count did not increase")
            
        if new_customer_payments > initial_customer_payments:
            print("✅ Customer payment total updated correctly")
        else:
            print("❌ Customer payment total not updated")
            
        return True
        
    except Exception as e:
        print(f"❌ Error creating payment: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_payment_system()
    if success:
        print("\n🎉 PAYMENT SYSTEM TEST PASSED!")
    else:
        print("\n💥 PAYMENT SYSTEM TEST FAILED!")
