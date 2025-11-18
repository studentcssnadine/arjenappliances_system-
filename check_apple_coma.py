#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# Setup Django
django.setup()

from myapp.models import Customer, CustomerItem, PaymentRecord
from decimal import Decimal

def check_apple_coma():
    print("=== CHECKING APPLE COMA'S ACCOUNT ===\n")
    
    # Find Apple Coma (case insensitive search)
    customers = Customer.objects.filter(customers_name__icontains='apple')
    
    if not customers:
        print("❌ No customers found with 'apple' in name")
        return
    
    for customer in customers:
        print(f"Found customer: {customer.customers_name}")
        print(f"ID: {customer.id}")
        print(f"Contact: {customer.contact}")
        print(f"Address: {customer.address}")
        print(f"Date Delivered: {customer.date_delivered}")
        print(f"Status: {customer.status}")
        print(f"Monthly Due: P{customer.monthly_due}")
        print(f"Term: {customer.term} months")
        print(f"Rebates: P{customer.rebates}")
        print(f"Amount (Contract): P{customer.amount}")
        print(f"Payments (Total): P{customer.payments}")
        print(f"Downpayment: P{customer.downpayment}")
        print(f"Balance: P{customer.balance}")
        print(f"Item (Legacy): {customer.item}")
        print("\n--- CUSTOMER ITEMS ---")
        
        # Check CustomerItem records
        customer_items = CustomerItem.objects.filter(customer=customer, status='active')
        if customer_items:
            for i, item in enumerate(customer_items, 1):
                print(f"Item {i}:")
                print(f"  Name: {item.item_name}")
                print(f"  Model: {item.item_model}")
                print(f"  Original Price: P{item.original_price}")
                print(f"  Downpayment: P{item.downpayment}")
                print(f"  Monthly Due: P{item.monthly_due}")
                print(f"  Term: {item.term_months} months")
                print(f"  Total Contract: P{item.total_contract_amount}")
                print(f"  Purchase Date: {item.purchase_date}")
                print(f"  Status: {item.status}")
                print()
        else:
            print("  No CustomerItem records found")
        
        print("--- PAYMENT RECORDS ---")
        
        # Check PaymentRecord entries
        payments = PaymentRecord.objects.filter(customer=customer).order_by('payment_date')
        if payments:
            total_paid = Decimal('0.00')
            total_rebates = Decimal('0.00')
            
            for payment in payments:
                print(f"Payment #{payment.payment_number}:")
                print(f"  Date: {payment.payment_date}")
                print(f"  Amount: P{payment.amount_paid}")
                print(f"  Method: {payment.payment_method}")
                print(f"  Rebate: P{payment.rebate_amount}")
                print(f"  Transaction: {payment.transaction_number}")
                print(f"  Customer Item: {payment.customer_item}")
                print()
                
                total_paid += payment.amount_paid
                total_rebates += payment.rebate_amount
            
            print(f"Total Payments: P{total_paid}")
            print(f"Total Rebates: P{total_rebates}")
            print(f"Total Paid (with rebates): P{total_paid + total_rebates}")
        else:
            print("  No PaymentRecord entries found")
        
        print("\n--- CALCULATION ANALYSIS ---")
        
        # Calculate what the dashboard should show
        if customer_items:
            total_contract = sum(item.total_contract_amount for item in customer_items)
            print(f"Sum of CustomerItem contracts: P{total_contract}")
        else:
            total_contract = (customer.monthly_due * customer.term) + customer.downpayment
            print(f"Legacy calculation (monthly * term + down): P{total_contract}")
        
        total_due = total_contract - customer.rebates
        print(f"Total due (contract - rebates): P{total_due}")
        
        payment_totals = PaymentRecord.objects.filter(customer=customer).aggregate(
            total_payments=django.db.models.Sum('amount_paid'),
            total_rebates=django.db.models.Sum('rebate_amount')
        )
        
        actual_total_paid = (payment_totals['total_payments'] or Decimal('0.00')) + (payment_totals['total_rebates'] or Decimal('0.00'))
        print(f"Actual total paid (payments + rebates): P{actual_total_paid}")
        
        remaining_balance = max(Decimal('0.00'), total_due - actual_total_paid)
        print(f"Calculated remaining balance: P{remaining_balance}")
        
        # Monthly calculation for current month
        from datetime import date
        current_month = date.today().month
        current_year = date.today().year
        
        this_month_payments = PaymentRecord.objects.filter(
            customer=customer,
            payment_date__month=current_month,
            payment_date__year=current_year
        )
        
        monthly_paid = sum(p.amount_paid + p.rebate_amount for p in this_month_payments)
        monthly_due = customer.monthly_due
        monthly_remaining = max(Decimal('0.00'), monthly_due - monthly_paid)
        
        print(f"\nMonthly billing for {date.today().strftime('%B %Y')}:")
        print(f"  Monthly due: P{monthly_due}")
        print(f"  Amount paid this month: P{monthly_paid}")
        print(f"  Remaining this month: P{monthly_remaining}")
        
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    check_apple_coma()
