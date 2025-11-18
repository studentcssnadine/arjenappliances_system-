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

print(f"=== FINAL ADMIN MATCH TEST ===")
print(f"Customer: {customer.customers_name}")

# Use EXACT same logic as admin
if customer_items:
    # Admin uses the FIRST ITEM's contract (monthly_due * term_months)
    first_item = customer_items[0]
    admin_total_contract = first_item.monthly_due * first_item.term_months
    admin_term = first_item.term_months
    print(f"Using FIRST ITEM: {first_item.item_name}")
    print(f"First item monthly_due: P{first_item.monthly_due}")
    print(f"First item term: {first_item.term_months}")
else:
    # For legacy customers, admin uses customer monthly_due * term
    admin_total_contract = customer.monthly_due * customer.term
    admin_term = customer.term
    print(f"Using CUSTOMER data")

total_paid_with_rebates = sum(payment.amount_paid + (payment.rebate_amount or 0) for payment in payments)

print(f"\nContract amount: P{admin_total_contract}")
print(f"Total paid + rebates: P{total_paid_with_rebates}")
print(f"Balance: P{admin_total_contract - total_paid_with_rebates}")
print(f"Term: {admin_term} months")
print(f"Payments made: {len(payments)}")
print(f"Payments remaining: {max(0, admin_term - len(payments))}")

progress = (len(payments) / admin_term * 100) if admin_term > 0 else 0
print(f"Progress: {progress:.1f}%")

print(f"\nThis should match admin payment history exactly!")
print(f"Expected: Balance P1,794.00, 3/3 payments, 100% complete")
