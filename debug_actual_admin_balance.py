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

print(f"=== ACTUAL ADMIN PAYMENT HISTORY BALANCE CALCULATION ===")
print(f"Customer: {customer.customers_name}")

# Get all payments for this customer
payments = PaymentRecord.objects.filter(customer=customer).select_related('customer_item').order_by('payment_date')

# Calculate payment summary using REAL ITEM DATA (not old customer data)
total_paid = sum(payment.amount_paid for payment in payments)
total_paid_with_rebates = sum(payment.amount_paid + (payment.rebate_amount or 0) for payment in payments)

print(f"Total paid: P{total_paid}")
print(f"Total paid with rebates: P{total_paid_with_rebates}")

# SMART FALLBACK: Use CustomerItem data if available, otherwise use clean Customer data
active_items = CustomerItem.objects.filter(customer=customer, status='active')

if active_items.exists():
    # Use the first active item's data (or sum all items if multiple)
    first_item = active_items.first()
    total_contract = first_item.monthly_due * first_item.term_months
    actual_term = first_item.term_months
    print(f"\nUsing FIRST ITEM data:")
    print(f"First item: {first_item.item_name}")
    print(f"First item monthly_due: P{first_item.monthly_due}")
    print(f"First item term_months: {first_item.term_months}")
    print(f"Total contract (first item): P{total_contract}")
else:
    # FALLBACK: Use Customer data but ensure it's not corrupted by payment recording
    # Use the ORIGINAL customer data, not the corrupted payment totals
    total_contract = customer.monthly_due * customer.term
    actual_term = customer.term
    print(f"\nUsing CUSTOMER data:")
    print(f"Customer monthly_due: P{customer.monthly_due}")
    print(f"Customer term: {customer.term}")
    print(f"Total contract (customer): P{total_contract}")

balance = total_contract - total_paid_with_rebates  # Correct: Contract - (Payments + Rebates)
payments_made = len(payments)
payments_remaining = max(0, actual_term - payments_made)

print(f"\n=== ADMIN BALANCE RESULT ===")
print(f"Balance: P{balance}")
print(f"Payments made: {payments_made}")
print(f"Payments remaining: {payments_remaining}")
print(f"Actual term: {actual_term}")

# Calculate progress percentage using actual term
progress_percentage = (payments_made / actual_term * 100) if actual_term > 0 else 0
print(f"Progress percentage: {progress_percentage:.1f}%")

print(f"\n=== ALL ACTIVE ITEMS ===")
for item in active_items:
    print(f"Item: {item.item_name} - Monthly Due: P{item.monthly_due}, Term: {item.term_months}")
