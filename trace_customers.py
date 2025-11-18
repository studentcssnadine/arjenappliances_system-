#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import CustomerHistory, Customer

print("=== PULLED OUT CUSTOMERS TRACE ===")
print(f"Total CustomerHistory records: {CustomerHistory.objects.count()}")
print(f"Pulled out records: {CustomerHistory.objects.filter(final_status='pulled_out').count()}")

print("\n=== RECENT PULLED OUT CUSTOMERS ===")
for record in CustomerHistory.objects.filter(final_status='pulled_out').order_by('-completion_date')[:10]:
    print(f"ID: {record.id} | {record.customers_name} | Item: {record.item_name} | Date: {record.completion_date} | TXN: {record.transaction_number}")

print("\n=== INACTIVE CUSTOMERS (status changed) ===")
print(f"Inactive customers: {Customer.objects.filter(status='inactive').count()}")
for customer in Customer.objects.filter(status='inactive')[:5]:
    print(f"ID: {customer.id} | {customer.customers_name} | Status: {customer.status}")

print("\n=== CUSTOMER LIST FILTER ===")
print(f"Active customers (shown in list): {Customer.objects.filter(status='active').count()}")
print(f"Total customers in database: {Customer.objects.count()}")
