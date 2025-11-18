#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import CustomerHistory, Customer
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()

print("=== TESTING CUSTOMERHISTORY CREATION ===")

# Get an inactive customer to test with
inactive_customer = Customer.objects.filter(status='inactive').first()
if not inactive_customer:
    print("No inactive customers found!")
    sys.exit(1)

print(f"Testing with customer: {inactive_customer.customers_name} (ID: {inactive_customer.id})")

# Get admin user
admin_user = User.objects.filter(role='admin').first()
if not admin_user:
    print("No admin user found!")
    sys.exit(1)

print(f"Using admin user: {admin_user.username}")

# Test CustomerHistory creation
try:
    print("\n=== ATTEMPTING CUSTOMERHISTORY CREATION ===")
    
    # Calculate remaining balance
    total_paid = Decimal('0.00')  # Simplified for testing
    remaining_balance = (inactive_customer.monthly_due * inactive_customer.term) - total_paid
    
    print(f"Customer data:")
    print(f"  - Name: {inactive_customer.customers_name}")
    print(f"  - Item: {inactive_customer.item}")
    print(f"  - Amount: {inactive_customer.amount}")
    print(f"  - Term: {inactive_customer.term}")
    print(f"  - Monthly Due: {inactive_customer.monthly_due}")
    print(f"  - Remaining Balance: {remaining_balance}")
    
    # Try to create CustomerHistory record
    history_record = CustomerHistory.objects.create(
        original_customer_id=inactive_customer.id,
        customers_name=inactive_customer.customers_name,
        address=inactive_customer.address,
        contact=inactive_customer.contact,
        date_delivered=inactive_customer.date_delivered or timezone.now().date(),
        completion_date=timezone.now().date(),
        total_amount=inactive_customer.amount,
        total_payments=remaining_balance,
        final_status='pulled_out',
        item_name=inactive_customer.item,
        item_model='Legacy Item',
        transaction_number=f'PULLOUT-{timezone.now().strftime("%Y%m%d")}-{inactive_customer.id:04d}',
        completed_by=admin_user,
        term=inactive_customer.term
    )
    
    print(f"\n✅ SUCCESS! Created CustomerHistory record ID: {history_record.id}")
    print(f"Transaction Number: {history_record.transaction_number}")
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

print(f"\n=== FINAL COUNT ===")
print(f"CustomerHistory records: {CustomerHistory.objects.count()}")
