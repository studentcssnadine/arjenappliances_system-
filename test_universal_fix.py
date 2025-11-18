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

def test_universal_payment_fix():
    print("=== TESTING UNIVERSAL PAYMENT ALLOCATION FIX ===\n")
    
    # Test with multiple customers
    customers = Customer.objects.filter(status='active')[:5]  # Test first 5 active customers
    
    for customer in customers:
        print(f"CUSTOMER: {customer.customers_name}")
        print(f"ID: {customer.id}")
        
        # Get customer items
        customer_items = CustomerItem.objects.filter(customer=customer, status='active')
        
        if customer_items:
            print(f"Items: {len(customer_items)} items")
            
            for i, item in enumerate(customer_items, 1):
                print(f"\n  Item {i}: {item.item_name}")
                
                # Get item-specific payments
                item_payments = PaymentRecord.objects.filter(customer=customer, customer_item=item)
                item_payment_totals = item_payments.aggregate(
                    total_payments=django.db.models.Sum('amount_paid'),
                    total_rebates=django.db.models.Sum('rebate_amount')
                )
                
                item_total_paid = (item_payment_totals['total_payments'] or Decimal('0.00')) + (item_payment_totals['total_rebates'] or Decimal('0.00'))
                
                # Get general payments
                general_payments = PaymentRecord.objects.filter(customer=customer, customer_item__isnull=True)
                general_payment_totals = general_payments.aggregate(
                    total_payments=django.db.models.Sum('amount_paid'),
                    total_rebates=django.db.models.Sum('rebate_amount')
                )
                
                general_total_paid = (general_payment_totals['total_payments'] or Decimal('0.00')) + (general_payment_totals['total_rebates'] or Decimal('0.00'))
                
                # Calculate proportional allocation
                total_contract = sum(item.total_contract_amount for item in customer_items)
                item_proportion = item.total_contract_amount / total_contract if total_contract > 0 else Decimal('1.00')
                
                if len(customer_items) > 1 and general_total_paid > 0:
                    item_general_allocation = general_total_paid * item_proportion
                else:
                    item_general_allocation = general_total_paid
                
                final_total_paid = item_total_paid + item_general_allocation
                item_total_due = item.total_contract_amount - (customer.rebates or Decimal('0.00')) * (item_proportion if len(customer_items) > 1 else Decimal('1.00'))
                remaining_balance = max(Decimal('0.00'), item_total_due - final_total_paid)
                
                # Determine status
                if remaining_balance <= 0:
                    status = 'FULLY PAID'
                elif final_total_paid > 0:
                    status = 'PARTIAL'
                else:
                    status = 'UNPAID'
                
                print(f"    Contract Amount: P{item.total_contract_amount}")
                print(f"    Item-specific Payments: P{item_total_paid}")
                print(f"    General Payment Allocation: P{item_general_allocation}")
                print(f"    Total Paid: P{final_total_paid}")
                print(f"    Remaining Balance: P{remaining_balance}")
                print(f"    Status: {status}")
        else:
            print("  Legacy customer (no CustomerItem records)")
            
            # Test legacy calculation
            all_payments = PaymentRecord.objects.filter(customer=customer)
            payment_totals = all_payments.aggregate(
                total_payments=django.db.models.Sum('amount_paid'),
                total_rebates=django.db.models.Sum('rebate_amount')
            )
            
            total_paid = (payment_totals['total_payments'] or Decimal('0.00')) + (payment_totals['total_rebates'] or Decimal('0.00'))
            total_contract = (customer.monthly_due * customer.term) + (customer.downpayment or Decimal('0.00'))
            item_total_due = total_contract - (customer.rebates or Decimal('0.00'))
            remaining_balance = max(Decimal('0.00'), item_total_due - total_paid)
            
            if remaining_balance <= 0:
                status = 'FULLY PAID'
            elif total_paid > 0:
                status = 'PARTIAL'
            else:
                status = 'UNPAID'
            
            print(f"    Item: {customer.item}")
            print(f"    Contract Amount: P{total_contract}")
            print(f"    Total Paid: P{total_paid}")
            print(f"    Remaining Balance: P{remaining_balance}")
            print(f"    Status: {status}")
        
        print("\n" + "-"*50 + "\n")

if __name__ == "__main__":
    import django.db.models
    test_universal_payment_fix()
