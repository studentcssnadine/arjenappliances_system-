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

def fix_all_customer_contracts():
    """Fix contract amounts for ALL customer items across the system"""
    
    print("Scanning all customer items for contract amount discrepancies...")
    
    # Get all active customer items
    all_items = CustomerItem.objects.filter(status='active')
    print(f"Found {all_items.count()} active customer items")
    
    fixed_count = 0
    total_checked = 0
    
    for item in all_items:
        total_checked += 1
        
        # Calculate what the contract should be
        calculated_contract = item.monthly_due * item.term_months if item.monthly_due and item.term_months else Decimal('0.00')
        current_contract = item.total_contract_amount or Decimal('0.00')
        
        print(f"\nItem {total_checked}: {item.item_name} (Customer: {item.customer.customers_name})")
        print(f"  Current contract: P{current_contract}")
        print(f"  Calculated contract: P{item.monthly_due} × {item.term_months} = P{calculated_contract}")
        
        # Check if there's a discrepancy
        if abs(current_contract - calculated_contract) > Decimal('0.01'):
            print(f"  [X] MISMATCH FOUND! Fixing...")
            
            # Update the contract amount
            item.total_contract_amount = calculated_contract
            item.save()
            
            fixed_count += 1
            print(f"  [OK] Fixed: Updated to P{calculated_contract}")
        else:
            print(f"  [OK] Contract amount is correct")
    
    print(f"\n" + "="*60)
    print(f"SUMMARY:")
    print(f"Total items checked: {total_checked}")
    print(f"Items fixed: {fixed_count}")
    print(f"Items already correct: {total_checked - fixed_count}")
    print(f"="*60)
    
    if fixed_count > 0:
        print(f"\n[OK] Successfully fixed {fixed_count} customer item contract amounts!")
        print("All customer items now have consistent contract calculations.")
    else:
        print(f"\n[OK] All customer items already had correct contract amounts!")

if __name__ == "__main__":
    fix_all_customer_contracts()
