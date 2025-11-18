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
all_payments = PaymentRecord.objects.filter(customer=customer)

print(f"=== CUSTOMER CONTEXT FIX TEST ===")
print(f"Customer: {customer.customers_name}")

# Calculate admin-style summary (same as admin payment history)
admin_total_paid = sum(payment.amount_paid for payment in all_payments)
admin_total_paid_with_rebates = sum(payment.amount_paid + (payment.rebate_amount or Decimal('0.00')) for payment in all_payments)

# Use same logic as admin for contract and balance
if customer_items:
    # Admin uses the FIRST ITEM's contract
    first_item = customer_items[0]
    admin_contract = first_item.monthly_due * first_item.term_months
    admin_actual_term = first_item.term_months
    print(f"Using FIRST ITEM: {first_item.item_name}")
else:
    # For legacy customers
    admin_contract = customer.monthly_due * customer.term
    admin_actual_term = customer.term
    print(f"Using CUSTOMER data")

admin_balance = admin_contract - admin_total_paid_with_rebates
admin_payments_made = len(all_payments)
admin_payments_remaining = max(0, admin_actual_term - admin_payments_made)
admin_progress_percentage = (admin_payments_made / admin_actual_term * 100) if admin_actual_term > 0 else 0

print(f"\n=== CUSTOMER CONTEXT VALUES ===")
print(f"total_contract_value: P{admin_contract}")
print(f"total_remaining_balance: P{admin_balance}")
print(f"total_paid: P{admin_total_paid_with_rebates}")
print(f"total_payments_made: {admin_payments_made}")
print(f"payments_remaining: {admin_payments_remaining}")
print(f"payment_percentage: {admin_progress_percentage:.1f}%")
print(f"total_term_months: {admin_actual_term}")

print(f"\n=== EXPECTED CUSTOMER DISPLAY ===")
print(f"Total Paid: P{admin_total_paid_with_rebates}")
print(f"Remaining Balance: P{admin_balance}")
print(f"Payments Made: {admin_payments_made} / {admin_actual_term}")
print(f"Payments Remaining: {admin_payments_remaining}")
print(f"Progress: {admin_progress_percentage:.0f}% Complete")

print(f"\nThis should now match admin payment history!")
print(f"Expected: Balance P1,794.00, 3/3 payments, 100% complete")
