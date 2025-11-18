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

from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from myapp.models import Customer, CustomUser
from myapp.views import customer_dashboard

def test_dashboard_loads():
    print("=== TESTING CUSTOMER DASHBOARD LOADING ===\n")
    
    # Create a test client
    client = Client()
    
    # Find Apple Coma customer
    try:
        customer = Customer.objects.get(customers_name__icontains='apple')
        print(f"Found customer: {customer.customers_name}")
        
        # Try to find their user account
        try:
            user = CustomUser.objects.get(customer_id=customer.id)
            print(f"Found user account: {user.username}")
            
            # Login as this user
            client.force_login(user)
            
            # Test dashboard access
            response = client.get('/customer-dashboard/')
            print(f"Dashboard response status: {response.status_code}")
            
            if response.status_code == 200:
                print("SUCCESS: Dashboard loads successfully!")
                print("SUCCESS: UnboundLocalError has been fixed!")
            else:
                print(f"ERROR: Dashboard failed to load: {response.status_code}")
                
        except CustomUser.DoesNotExist:
            print("ERROR: No user account found for this customer")
            
    except Customer.DoesNotExist:
        print("ERROR: Apple Coma customer not found")
    
    print("\n" + "="*50)

if __name__ == "__main__":
    test_dashboard_loads()
