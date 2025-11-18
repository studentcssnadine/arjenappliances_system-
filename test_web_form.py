#!/usr/bin/env python
import os
import sys
import django
from datetime import date
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from myapp.models import Customer, PaymentRecord

def test_web_form():
    print("=== TESTING WEB FORM SUBMISSION ===\n")
    
    # Create a test client
    client = Client()
    
    # Get a user and customer for testing
    User = get_user_model()
    user = User.objects.filter(is_active=True).first()
    customer = Customer.objects.filter(status='active').first()
    
    if not user or not customer:
        print("❌ Missing user or customer for testing")
        return False
    
    print(f"Testing with user: {user.username}")
    print(f"Testing with customer: {customer.customers_name}")
    
    # Login the user
    client.force_login(user)
    
    # Get initial counts
    initial_count = PaymentRecord.objects.count()
    initial_customer_payments = customer.payments
    
    print(f"Initial payment count: {initial_count}")
    print(f"Initial customer payments: ₱{initial_customer_payments}")
    
    # Test form submission
    form_data = {
        'customer_id': customer.id,
        'payment_date': date.today().strftime('%Y-%m-%d'),
        'amount_paid': '2000.00',
        'payment_method': 'Cash',
        'rebate_applied': 'Yes',
        'rebate_amount': '150.00',
        'notes': 'Test payment via web form',
        'add_payment': 'Record Payment'
    }
    
    print(f"\nSubmitting form data: {form_data}")
    
    try:
        # Submit the form
        response = client.post('/payments/record/', form_data, follow=True)
        
        print(f"Response status: {response.status_code}")
        print(f"Final URL: {response.request['PATH_INFO']}")
        
        # Check if payment was created
        final_count = PaymentRecord.objects.count()
        print(f"Final payment count: {final_count}")
        
        if final_count > initial_count:
            # Get the new payment
            new_payment = PaymentRecord.objects.latest('created_at')
            print(f"✅ New payment created:")
            print(f"   - ID: {new_payment.id}")
            print(f"   - Transaction: {new_payment.transaction_number}")
            print(f"   - Amount: ₱{new_payment.amount_paid}")
            print(f"   - Rebate: ₱{new_payment.rebate_amount}")
            
            # Check customer update
            customer.refresh_from_db()
            final_customer_payments = customer.payments
            print(f"   - Customer payments: ₱{initial_customer_payments} → ₱{final_customer_payments}")
            
            # Check for success message
            messages = list(response.context['messages']) if response.context and 'messages' in response.context else []
            if messages:
                for message in messages:
                    print(f"   - Message: {message}")
            
            return True
        else:
            print("❌ No new payment was created")
            # Print response content for debugging
            print("Response content:")
            print(response.content.decode()[:500])
            return False
            
    except Exception as e:
        print(f"❌ Error submitting form: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_web_form()
    if success:
        print("\n🎉 WEB FORM TEST PASSED!")
    else:
        print("\n💥 WEB FORM TEST FAILED!")
