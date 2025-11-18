import os
import django
import sys

# Add the project directory to the Python path
sys.path.append(r'C:\Users\ACER\Desktop\arjenappliances_system\myproject')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import Customer, PaymentRecord, CustomerItem
from decimal import Decimal

def debug_customer_balance():
    """Debug the customer balance calculation to match admin view"""
    
    # Get the customer (assuming this is for Apple Coma based on the screenshot)
    try:
        customer = Customer.objects.get(customers_name__icontains="Apple")
        print(f"Customer: {customer.customers_name}")
        print(f"Customer ID: {customer.id}")
        
        # Get customer items
        customer_items = CustomerItem.objects.filter(customer=customer, status='active')
        print(f"\nCustomer Items: {customer_items.count()}")
        
        for item in customer_items:
            print(f"- {item.item_name}: Monthly P{item.monthly_due}, Term {item.term_months} months")
            print(f"  Contract: P{item.monthly_due * item.term_months}")
            print(f"  Total Contract Amount: P{item.total_contract_amount}")
            
            # Check item-specific payments
            item_payments = PaymentRecord.objects.filter(customer=customer, customer_item=item)
            item_total_paid = sum(p.amount_paid + (p.rebate_amount or 0) for p in item_payments)
            print(f"  Item-specific payments: P{item_total_paid}")
            print(f"  Item balance: P{item.total_contract_amount - item_total_paid}")
        
        # Get all payments
        payments = PaymentRecord.objects.filter(customer=customer).order_by('payment_date')
        print(f"\nPayment Records: {payments.count()}")
        
        total_paid = Decimal('0.00')
        total_rebates = Decimal('0.00')
        
        for payment in payments:
            total_paid += payment.amount_paid
            if payment.rebate_amount:
                total_rebates += payment.rebate_amount
            print(f"- {payment.payment_date}: P{payment.amount_paid} paid, P{payment.rebate_amount or 0} rebate")
        
        print(f"\nTotals:")
        print(f"Total Paid: P{total_paid}")
        print(f"Total Rebates: P{total_rebates}")
        print(f"Total Paid + Rebates: P{total_paid + total_rebates}")
        
        # Calculate contract like admin does (first item)
        if customer_items:
            first_item = customer_items.first()
            admin_contract = first_item.monthly_due * first_item.term_months
            print(f"\nAdmin Contract Calculation (First Item):")
            print(f"P{first_item.monthly_due} × {first_item.term_months} = P{admin_contract}")
        else:
            admin_contract = customer.monthly_due * customer.term
            print(f"\nFallback Contract Calculation:")
            print(f"P{customer.monthly_due} × {customer.term} = P{admin_contract}")
        
        # Calculate balance like admin does
        admin_balance = admin_contract - (total_paid + total_rebates)
        print(f"\nAdmin Balance Calculation:")
        print(f"P{admin_contract} - P{total_paid + total_rebates} = P{admin_balance}")
        
        # Check what the customer view currently shows
        print(f"\nExpected Balance (should match admin): P{admin_balance}")
        print(f"This should be P6,549 based on the payment records")
        
    except Customer.DoesNotExist:
        print("Customer not found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_customer_balance()
