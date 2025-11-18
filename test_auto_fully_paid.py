#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import Customer, PaymentRecord, CustomerHistory
from django.contrib.auth import get_user_model
from django.db.models import Sum
from decimal import Decimal

User = get_user_model()

print("=== TESTING AUTO FULLY PAID DETECTION ===")

# Get admin user
admin_user = User.objects.filter(role='admin').first()
if not admin_user:
    print("No admin user found!")
    sys.exit(1)

print(f"Using admin user: {admin_user.username}")

# Check all active customers for fully paid status
active_customers = Customer.objects.filter(status='active')
print(f"\nChecking {active_customers.count()} active customers...")

moved_customers = []

for customer in active_customers:
    # Calculate remaining balance
    total_paid = PaymentRecord.objects.filter(customer=customer).aggregate(
        total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_contract = customer.monthly_due * customer.term
    remaining_balance = total_contract - total_paid
    
    print(f"\n{customer.customers_name}:")
    print(f"  Contract: ₱{total_contract}")
    print(f"  Paid: ₱{total_paid}")
    print(f"  Remaining: ₱{remaining_balance}")
    
    # If remaining balance is 0 or negative, customer should be moved
    if remaining_balance <= Decimal('0.00'):
        print(f"  ✅ FULLY PAID - Should be moved to Customer History")
        
        # Get the last payment transaction number
        last_payment = PaymentRecord.objects.filter(customer=customer).order_by('-payment_date').first()
        transaction_number = last_payment.transaction_number if last_payment and last_payment.transaction_number else f'FULLYPAID-{customer.id:04d}'
        
        print(f"  Last payment transaction: {transaction_number}")
        
        # Check if CustomerHistory already exists
        existing_history = CustomerHistory.objects.filter(original_customer_id=customer.id).first()
        if existing_history:
            print(f"  ⚠️ CustomerHistory already exists: {existing_history.final_status}")
        else:
            print(f"  🔄 Creating CustomerHistory record...")
            
            # Import the function from views
            from myapp.views import check_and_move_fully_paid_customer
            
            # Use the function to move the customer
            was_moved = check_and_move_fully_paid_customer(customer, admin_user)
            
            if was_moved:
                print(f"  ✅ Successfully moved to Customer History")
                moved_customers.append(customer.customers_name)
            else:
                print(f"  ❌ Failed to move customer")
    else:
        print(f"  ⏳ Still has remaining balance")

print(f"\n=== SUMMARY ===")
print(f"Customers moved to Customer History: {len(moved_customers)}")
for name in moved_customers:
    print(f"  - {name}")

print(f"\n=== FINAL COUNTS ===")
print(f"Active customers: {Customer.objects.filter(status='active').count()}")
print(f"Fully paid customers: {Customer.objects.filter(status='fully_paid').count()}")
print(f"CustomerHistory fully paid records: {CustomerHistory.objects.filter(final_status='fully_paid').count()}")

print(f"\n=== CUSTOMER HISTORY FULLY PAID RECORDS ===")
for record in CustomerHistory.objects.filter(final_status='fully_paid'):
    print(f"{record.customers_name} | {record.item_name} | {record.transaction_number} | ₱{record.total_payments}")
