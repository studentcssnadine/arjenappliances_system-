import os
import django
import sys
from dateutil.relativedelta import relativedelta

# Add the project directory to the Python path
sys.path.append(r'C:\Users\ACER\Desktop\arjenappliances_system\myproject')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myapp.models import Customer, CustomerItem

def fix_all_due_dates():
    """Fix due dates for ALL customer items to match admin payment history logic"""
    
    print("Fixing due dates for all customer items...")
    print("Logic: First due date = delivery date + 1 month")
    
    # Get all active customer items
    all_items = CustomerItem.objects.filter(status='active')
    print(f"Found {all_items.count()} active customer items")
    
    fixed_count = 0
    total_checked = 0
    
    for item in all_items:
        total_checked += 1
        
        # Calculate what the first due date should be (delivery + 1 month)
        if item.purchase_date:  # This is the delivery date
            correct_first_due = item.purchase_date + relativedelta(months=1)
            current_first_due = item.first_due_date
            
            print(f"\nItem {total_checked}: {item.item_name} (Customer: {item.customer.customers_name})")
            print(f"  Delivery Date: {item.purchase_date}")
            print(f"  Current First Due: {current_first_due}")
            print(f"  Correct First Due: {correct_first_due}")
            
            # Check if there's a discrepancy
            if current_first_due != correct_first_due:
                print(f"  [X] MISMATCH FOUND! Fixing...")
                
                # Update the first due date
                item.first_due_date = correct_first_due
                item.save()
                
                fixed_count += 1
                print(f"  [OK] Fixed: Updated to {correct_first_due}")
            else:
                print(f"  [OK] Due date is correct")
        else:
            print(f"\nItem {total_checked}: {item.item_name} - NO DELIVERY DATE SET")
    
    print(f"\n" + "="*60)
    print(f"SUMMARY:")
    print(f"Total items checked: {total_checked}")
    print(f"Items fixed: {fixed_count}")
    print(f"Items already correct: {total_checked - fixed_count}")
    print(f"="*60)
    
    if fixed_count > 0:
        print(f"\n[OK] Successfully fixed {fixed_count} customer item due dates!")
        print("All customer items now have correct due date calculations.")
    else:
        print(f"\n[OK] All customer items already had correct due dates!")

if __name__ == "__main__":
    fix_all_due_dates()
