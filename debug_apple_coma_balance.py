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

print(f"=== APPLE COMA DEBUG ===")
print(f"Customer ID: {customer.id}")
print(f"Monthly Due: {customer.monthly_due}")
print(f"Term: {customer.term}")
print(f"Rebates: {customer.rebates}")

# Check if multi-item or legacy
customer_items = CustomerItem.objects.filter(customer=customer, status='active')
print(f"\nCustomer Items Count: {customer_items.count()}")

if customer_items:
    print("=== MULTI-ITEM CUSTOMER ===")
    total_contract = Decimal('0.00')
    for item in customer_items:
        print(f"Item: {item.item_name} {item.item_model}")
        print(f"  Contract Amount: {item.total_contract_amount}")
        print(f"  Term: {item.term_months}")
        total_contract += item.total_contract_amount
    print(f"Total Contract (Items): {total_contract}")
else:
    print("=== LEGACY CUSTOMER ===")
    total_contract = customer.monthly_due * customer.term
    print(f"Total Contract (Legacy): {total_contract}")

# Check payments
payments = PaymentRecord.objects.filter(customer=customer)
total_paid = sum(p.amount_paid for p in payments)
total_rebates = sum(p.rebate_amount or Decimal('0.00') for p in payments)
total_paid_with_rebates = total_paid + total_rebates

print(f"\n=== PAYMENTS ===")
print(f"Payment Records: {payments.count()}")
print(f"Total Paid: {total_paid}")
print(f"Total Rebates: {total_rebates}")
print(f"Total Paid + Rebates: {total_paid_with_rebates}")

# Calculate balance like admin
admin_balance = total_contract - total_paid_with_rebates
print(f"\n=== BALANCE CALCULATION ===")
print(f"Admin Balance: {admin_balance}")
print(f"Expected: P6,549.00")

# Check individual payments
print(f"\n=== PAYMENT DETAILS ===")
for i, payment in enumerate(payments.order_by('payment_date'), 1):
    print(f"Payment {i}: {payment.payment_date} - P{payment.amount_paid} (Rebate: P{payment.rebate_amount or 0})")

# Now test the NEW calculation method
print(f"\n=== NEW CALCULATION (Customer Monthly Due * Term) ===")
new_total_contract = customer.monthly_due * customer.term
new_balance = new_total_contract - total_paid_with_rebates
print(f"Customer Monthly Due: {customer.monthly_due}")
print(f"Customer Term: {customer.term}")
print(f"New Total Contract: {new_total_contract}")
print(f"New Balance: {new_balance}")
print(f"Should match admin: P6,549.00")
