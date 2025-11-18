#!/usr/bin/env python
import os
import sys
import django

# Setup Django
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import PaymentRecord, Customer, CustomerItem

# Find Trisha
try:
    customer = Customer.objects.get(customers_name__icontains="Trisha")
    print(f"Customer: {customer.customers_name} (ID: {customer.id})")
    
    # Get all payments for Trisha
    payments = PaymentRecord.objects.filter(customer=customer)
    print(f"Total payments found: {payments.count()}")
    
    for p in payments:
        print(f"Payment ID: {p.id}")
        print(f"  Date: {p.payment_date}")
        print(f"  Amount: {p.amount_paid}")
        print(f"  Customer Item: {p.customer_item}")
        print(f"  Customer Item ID: {p.customer_item.id if p.customer_item else 'None'}")
        print("---")
    
    # Get Trisha's items
    items = CustomerItem.objects.filter(customer=customer)
    print(f"Customer items found: {items.count()}")
    for item in items:
        print(f"Item: {item.item_name} {item.item_model} (ID: {item.id})")
        
except Exception as e:
    print(f"Error: {e}")
