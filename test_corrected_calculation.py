import os
import django
import sys

# Add the project directory to Python path
sys.path.append('c:/Users/ACER/Desktop/arjenappliances_system/myproject')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import Customer, CustomerItem, PaymentRecord
from decimal import Decimal

# Get Apple Coma customer
customer = Customer.objects.get(customers_name='Apple Coma')
customer_items = CustomerItem.objects.filter(customer=customer, status='active')
payments = PaymentRecord.objects.filter(customer=customer).order_by('payment_date')

print(f"=== CORRECTED CALCULATION TEST ===")
print(f"Customer: {customer.customers_name}")

# Use EXACT same logic as admin
if customer_items:
    # For multi-item customers, admin uses sum of individual contracts
    admin_total_contract = sum(item.total_contract_amount for item in customer_items)
    print(f"Multi-item customer - using sum of contracts")
else:
    # For legacy customers, admin uses customer monthly_due * term
    admin_total_contract = customer.monthly_due * customer.term
    print(f"Legacy customer - using monthly_due * term")

total_paid_with_rebates = sum(payment.amount_paid + (payment.rebate_amount or 0) for payment in payments)

print(f"\nContract amount: P{admin_total_contract}")
print(f"Total paid + rebates: P{total_paid_with_rebates}")
print(f"Balance: P{admin_total_contract - total_paid_with_rebates}")

print(f"\nThis should match admin payment history balance!")
print(f"Expected from admin debug: P23,121.00")
