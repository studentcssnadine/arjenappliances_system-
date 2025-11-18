import os
import django
import sys

# Add the project directory to the Python path
sys.path.append(r'C:\Users\ACER\Desktop\arjenappliances_system\myproject')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import Customer, CustomerItem
from decimal import Decimal

def fix_haier_contract():
    """Fix the Haier Ref contract amount to match calculated value"""
    
    try:
        customer = Customer.objects.get(customers_name__icontains="Apple")
        print(f"Customer: {customer.customers_name}")
        
        # Get Haier Ref item
        haier_item = CustomerItem.objects.get(customer=customer, item_name__icontains="Haier")
        print(f"\nHaier Item: {haier_item.item_name}")
        print(f"Current total_contract_amount: P{haier_item.total_contract_amount}")
        print(f"Monthly due: P{haier_item.monthly_due}")
        print(f"Term: {haier_item.term_months} months")
        
        # Calculate correct contract amount
        correct_contract = haier_item.monthly_due * haier_item.term_months
        print(f"Calculated contract: P{haier_item.monthly_due} × {haier_item.term_months} = P{correct_contract}")
        
        # Update the contract amount
        haier_item.total_contract_amount = correct_contract
        haier_item.save()
        
        print(f"\nUpdated Haier Ref total_contract_amount to P{correct_contract}")
        print("The balance should now show P0 since no payments are assigned to this item")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_haier_contract()
