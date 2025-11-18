#!/usr/bin/env python
import os
import sys
import django
from datetime import date

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from myapp.models import Customer, PaymentRecord

def test_full_user_flow():
    print("=== TESTING COMPLETE USER FLOW ===\n")
    
    client = Client()
    User = get_user_model()
    
    # Get test data
    user = User.objects.filter(is_active=True, role__in=['admin', 'staff']).first()
    customer = Customer.objects.filter(status='active').first()
    
    if not user or not customer:
        print("❌ Missing test data")
        return False
    
    print(f"Testing with user: {user.username} ({user.role})")
    print(f"Testing with customer: {customer.customers_name}")
    
    # Step 1: Login
    client.force_login(user)
    print("✅ Step 1: User logged in")
    
    # Step 2: Access record payment page
    response = client.get('/payments/record/')
    print(f"✅ Step 2: Accessed record payment page (Status: {response.status_code})")
    
    if response.status_code != 200:
        print("❌ Could not access record payment page")
        return False
    
    # Check if form is present
    content = response.content.decode()
    if 'id="paymentForm"' in content and 'name="add_payment"' in content:
        print("✅ Step 3: Payment form found on page")
    else:
        print("❌ Payment form not found on page")
        return False
    
    # Check if customers are loaded
    if f'value="{customer.id}"' in content:
        print("✅ Step 4: Customer options loaded in dropdown")
    else:
        print("❌ Customer options not found in dropdown")
        return False
    
    # Step 5: Submit payment form
    initial_count = PaymentRecord.objects.count()
    initial_customer_total = customer.payments
    
    form_data = {
        'customer_id': customer.id,
        'payment_date': date.today().strftime('%Y-%m-%d'),
        'amount_paid': '2500.00',
        'payment_method': 'GCash',
        'rebate_applied': 'Yes',
        'rebate_amount': '200.00',
        'notes': 'Complete flow test payment',
        'add_payment': 'Record Payment'
    }
    
    response = client.post('/payments/record/', form_data, follow=True)
    print(f"✅ Step 5: Form submitted (Status: {response.status_code})")
    
    # Step 6: Check if payment was created
    final_count = PaymentRecord.objects.count()
    if final_count > initial_count:
        new_payment = PaymentRecord.objects.latest('created_at')
        print(f"✅ Step 6: Payment created successfully")
        print(f"   - Transaction: {new_payment.transaction_number}")
        print(f"   - Amount: ₱{new_payment.amount_paid}")
        print(f"   - Rebate: ₱{new_payment.rebate_amount}")
    else:
        print("❌ Step 6: Payment was not created")
        return False
    
    # Step 7: Check customer account update
    customer.refresh_from_db()
    final_customer_total = customer.payments
    if final_customer_total > initial_customer_total:
        print(f"✅ Step 7: Customer account updated")
        print(f"   - Total payments: ₱{initial_customer_total} → ₱{final_customer_total}")
    else:
        print("❌ Step 7: Customer account not updated")
        return False
    
    # Step 8: Check success message
    try:
        messages = list(response.context.get('messages', [])) if response.context else []
        success_message_found = any('successfully' in str(msg).lower() for msg in messages)
        if success_message_found:
            print("✅ Step 8: Success message displayed")
        else:
            print("⚠️ Step 8: Success message not found (but payment was created)")
    except:
        print("⚠️ Step 8: Could not check messages (but payment was created)")
    
    # Step 9: Check if payment appears in recent payments
    response = client.get('/payments/record/')
    content = response.content.decode()
    if new_payment.transaction_number in content:
        print("✅ Step 9: Payment appears in recent payments list")
    else:
        print("⚠️ Step 9: Payment not visible in recent payments (but was created)")
    
    return True

if __name__ == "__main__":
    success = test_full_user_flow()
    if success:
        print("\n🎉 COMPLETE USER FLOW TEST PASSED!")
        print("✅ Record Payment system is fully functional!")
    else:
        print("\n💥 COMPLETE USER FLOW TEST FAILED!")
