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

print(f"=== ADMIN PAYMENT HISTORY VIEW SIMULATION ===")
print(f"Customer: {customer.customers_name}")

# Get all payments for this customer (for overall summary and breakdown)
payments = PaymentRecord.objects.filter(customer=customer).select_related('customer_item').order_by('payment_date')

# Calculate payment summary using REAL ITEM DATA (not old customer data)
total_paid = sum(payment.amount_paid for payment in payments)
total_paid_with_rebates = sum(payment.amount_paid + (payment.rebate_amount or 0) for payment in payments)

print(f"\nPayments found: {payments.count()}")
print(f"Total paid: P{total_paid}")
print(f"Total paid with rebates: P{total_paid_with_rebates}")

# Check if customer has items in CustomerItem table
active_items = CustomerItem.objects.filter(customer=customer, status='active')

if active_items.exists():
    print(f"\n=== MULTI-ITEM CUSTOMER (Admin Logic) ===")
    print(f"Active items: {active_items.count()}")
    
    # Admin uses CustomerItem data when available
    total_contract = sum(item.total_contract_amount for item in active_items)
    actual_term = max(item.term_months for item in active_items) if active_items else customer.term
    
    print(f"Total contract (from items): P{total_contract}")
    print(f"Actual term (max from items): {actual_term}")
else:
    print(f"\n=== LEGACY CUSTOMER (Admin Logic) ===")
    # FALLBACK: Use Customer data but ensure it's not corrupted by payment recording
    # Use the ORIGINAL customer data, not the corrupted payment totals
    total_contract = customer.monthly_due * customer.term
    actual_term = customer.term
    
    print(f"Total contract (customer): P{total_contract}")
    print(f"Actual term (customer): {actual_term}")

balance = total_contract - total_paid_with_rebates  # Correct: Contract - (Payments + Rebates)
payments_made = len(payments)
payments_remaining = max(0, actual_term - payments_made)

print(f"\n=== ADMIN CALCULATION RESULT ===")
print(f"Balance: P{balance}")
print(f"Payments made: {payments_made}")
print(f"Payments remaining: {payments_remaining}")

# Calculate progress percentage using actual term
progress_percentage = (payments_made / actual_term * 100) if actual_term > 0 else 0
print(f"Progress percentage: {progress_percentage:.1f}%")

print(f"\n=== PAYMENT DETAILS ===")
for i, payment in enumerate(payments, 1):
    rebate_text = f" (Rebate: P{payment.rebate_amount})" if payment.rebate_amount else ""
    item_text = f" [{payment.customer_item.item_name}]" if payment.customer_item else " [General]"
    print(f"Payment {i}: {payment.payment_date} - P{payment.amount_paid}{rebate_text}{item_text}")
