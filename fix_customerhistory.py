#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import CustomerHistory, Customer, PaymentRecord
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum

User = get_user_model()

print("=== FIXING CUSTOMERHISTORY FOR PULLED OUT CUSTOMERS ===")

# Get all inactive customers
inactive_customers = Customer.objects.filter(status='inactive')
print(f"Found {inactive_customers.count()} inactive customers")

# Get admin user
admin_user = User.objects.filter(role='admin').first()
if not admin_user:
    print("No admin user found!")
    sys.exit(1)

print(f"Using admin user: {admin_user.username}")

created_count = 0

for customer in inactive_customers:
    # Check if CustomerHistory already exists for this customer
    existing = CustomerHistory.objects.filter(original_customer_id=customer.id).first()
    if existing:
        print(f"SKIP: {customer.customers_name} - CustomerHistory already exists")
        continue
    
    try:
        # Calculate remaining balance
        total_paid = PaymentRecord.objects.filter(customer=customer).aggregate(
            total=Sum('amount_paid'))['total'] or Decimal('0.00')
        remaining_balance = (customer.monthly_due * customer.term) - total_paid
        
        # Create CustomerHistory record
        history_record = CustomerHistory.objects.create(
            original_customer_id=customer.id,
            customers_name=customer.customers_name,
            address=customer.address,
            contact=customer.contact,
            date_delivered=customer.date_delivered or timezone.now().date(),
            completion_date=customer.completion_date or timezone.now().date(),
            total_amount=customer.amount,
            total_payments=remaining_balance,
            final_status='pulled_out',
            item_name=customer.item,
            item_model='Legacy Item',
            transaction_number=f'PULLOUT-{timezone.now().strftime("%Y%m%d")}-{customer.id:04d}',
            completed_by=admin_user,
            term=customer.term
        )
        
        print(f"SUCCESS: Created CustomerHistory for {customer.customers_name} (ID: {history_record.id})")
        created_count += 1
        
    except Exception as e:
        print(f"ERROR creating CustomerHistory for {customer.customers_name}: {str(e)}")

print(f"\n=== SUMMARY ===")
print(f"Created {created_count} CustomerHistory records")
print(f"Total CustomerHistory records now: {CustomerHistory.objects.count()}")
print(f"Pulled out records: {CustomerHistory.objects.filter(final_status='pulled_out').count()}")

print("\n=== PULLED OUT CUSTOMERS IN HISTORY ===")
for record in CustomerHistory.objects.filter(final_status='pulled_out').order_by('-completion_date'):
    print(f"{record.customers_name} | {record.item_name} | {record.transaction_number}")
