#!/usr/bin/env python
import os
import sys
import django
from datetime import date, datetime
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import Customer, PaymentRecord, CustomUser

def simulate_web_form_processing():
    print("=== SIMULATING EXACT WEB FORM PROCESSING ===\n")
    
    # Get test data
    customer = Customer.objects.filter(status='active').first()
    user = CustomUser.objects.filter(is_active=True).first()
    
    if not customer or not user:
        print("❌ Missing test data")
        return
    
    print(f"Testing with customer: {customer.customers_name} (ID: {customer.id})")
    print(f"Testing with user: {user.username}")
    
    # Simulate the exact form data processing from the view
    try:
        print("\n=== SIMULATING VIEW PROCESSING ===")
        
        # Simulate form data (as it comes from request.POST)
        customer_id = str(customer.id)  # Form data comes as strings
        payment_date_str = '2025-11-02'
        amount_paid = '1000.00'  # Form data comes as strings
        payment_method = 'Cash'
        rebate_applied = 'Yes'
        rebate_amount_input = '50.00'
        notes = 'Test web form simulation'
        
        print(f"Form data: customer_id={customer_id}, payment_date={payment_date_str}, amount={amount_paid}")
        
        # Convert payment_date string to date object (as in the view)
        try:
            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            payment_date = datetime.now().date()
        
        print(f"Converted payment_date: {payment_date}")
        
        # Get customer object (as in the view)
        customer_obj = Customer.objects.get(id=customer_id)
        print(f"Customer object: {customer_obj.customers_name}")
        
        # Handle rebate amount (as in the view)
        rebate_amount = Decimal('0.00')
        has_rebate = rebate_applied == 'Yes'
        if has_rebate and rebate_amount_input:
            try:
                rebate_amount = Decimal(rebate_amount_input)
            except (ValueError, TypeError):
                rebate_amount = Decimal('0.00')
        
        print(f"Rebate processing: has_rebate={has_rebate}, rebate_amount={rebate_amount}")
        
        # Create payment record exactly as in the view
        print("\nCreating PaymentRecord with objects.create()...")
        payment = PaymentRecord.objects.create(
            customer=customer_obj,
            payment_date=payment_date,
            amount_paid=Decimal(amount_paid),
            payment_method=payment_method,
            recorded_by=user,
            has_rebate=has_rebate,
            rebate_amount=rebate_amount,
            notes=notes
        )
        
        print(f"✅ SUCCESS! Payment created:")
        print(f"   - ID: {payment.id}")
        print(f"   - Transaction: {payment.transaction_number}")
        print(f"   - Payment Number: {payment.payment_number}")
        print(f"   - Amount: ₱{payment.amount_paid}")
        print(f"   - Rebate: ₱{payment.rebate_amount}")
        
        # Check customer update
        customer_obj.refresh_from_db()
        print(f"   - Customer total payments: ₱{customer_obj.payments}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR in web form simulation: {str(e)}")
        import traceback
        print(f"Full traceback:\n{traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = simulate_web_form_processing()
    
    if success:
        print("\n🎉 WEB FORM SIMULATION SUCCESSFUL!")
        print("The issue might be in the actual web request handling.")
    else:
        print("\n💥 WEB FORM SIMULATION FAILED!")
        print("The issue is in the payment creation logic.")
