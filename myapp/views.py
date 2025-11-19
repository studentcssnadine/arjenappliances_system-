from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Sum, Count, F, Case, When
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import json
import logging
import re
from .models import (
    CustomUser, Customer, PaymentRecord, CustomerItem, 
    Transaction, MonthlyStatement, UserActivityLog, CustomerHistory
)

from .forms import (
    CustomerRegistrationForm, CustomerForm, PaymentForm, 
    CustomUserCreationForm, CustomUserEditForm
)

# Get logger for this module
logger = logging.getLogger('myapp')

def calculate_monthly_billing(customer, month, year):
    """Calculate monthly billing information matching PHP calculateMonthlyBilling function"""
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    # Get payments for this specific month
    month_payments = PaymentRecord.objects.filter(
        customer=customer,
        payment_date__month=month,
        payment_date__year=year
    )
    
    amount_paid = month_payments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    # Calculate due date (end of month)
    due_date = datetime(year, month, 1) + relativedelta(months=1) - timedelta(days=1)
    
    # Determine total due for this month
    total_due = customer.monthly_due
    
    # Calculate remaining balance
    remaining_balance = total_due - amount_paid
    
    # Determine status
    if amount_paid >= total_due:
        status = 'paid'
    elif amount_paid > 0:
        status = 'partial'
    else:
        # Check if overdue
        current_date = timezone.now().date()
        if due_date.date() < current_date:
            status = 'overdue'
        else:
            status = 'unpaid'
    
    return {
        'total_due': total_due,
        'amount_paid': amount_paid,
        'remaining_balance': remaining_balance,
        'due_date': due_date.date(),
        'status': status
    }

def generate_transaction_number():
    """Generate unique transaction number with proper collision handling"""
    from datetime import datetime
    from .models import PaymentRecord
    
    current_date = datetime.now()
    year = current_date.year
    month = current_date.month
    
    # Find the next available number to avoid conflicts
    counter = 1
    while True:
        txn_number = f"TXN-{year}-{month:02d}-{counter:04d}"
        # Check if this transaction number already exists
        if not PaymentRecord.objects.filter(transaction_number=txn_number).exists():
            return txn_number
        counter += 1
        
        # Safety check to prevent infinite loop
        if counter > 9999:
            # Fallback to timestamp-based number
            timestamp = current_date.strftime('%H%M%S')
            return f"TXN-{year}-{month:02d}-{timestamp}"

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def extract_item_model(item_name):
    """Extract model from item name"""
    if not item_name:
        return "Unknown Model"
    
    item_name = item_name.strip()
    
    # Pattern 1: Alphanumeric with dashes/underscores (SDT-7586, ASTRN_09)
    model_pattern1 = re.search(r'([A-Z0-9_-]+(?:\d+[A-Z]*|[A-Z]+\d+))\s*$', item_name)
    if model_pattern1:
        return model_pattern1.group(1)
    
    # Pattern 2: Numbers with letters (012-A)
    model_pattern2 = re.search(r'(\d+-[A-Z]+)\s*$', item_name)
    if model_pattern2:
        return model_pattern2.group(1)
    
    # Pattern 3: Last word if it looks like a model
    words = item_name.split()
    if len(words) > 1:
        last_word = words[-1]
        if re.search(r'[0-9_-]', last_word):
            return last_word
    
    # Fallback: use last 2 words or "Generic Model"
    if len(words) >= 2:
        return ' '.join(words[-2:])
    
    return "Generic Model"

def check_and_move_fully_paid_customer(customer, request_user):
    """Check if customer is fully paid and move to CustomerHistory if so"""
    try:
        # Calculate remaining balance
        total_paid = PaymentRecord.objects.filter(customer=customer).aggregate(
            total=Sum('amount_paid'))['total'] or Decimal('0.00')
        total_contract = customer.monthly_due * customer.term
        remaining_balance = total_contract - total_paid
        
        # If remaining balance is 0 or negative, customer is fully paid
        if remaining_balance <= Decimal('0.00'):
            # Get the last payment transaction number
            last_payment = PaymentRecord.objects.filter(customer=customer).order_by('-payment_date').first()
            transaction_number = last_payment.transaction_number if last_payment and last_payment.transaction_number else f'FULLYPAID-{timezone.now().strftime("%Y%m%d")}-{customer.id:04d}'
            
            # Check if CustomerHistory already exists for this customer
            existing_history = CustomerHistory.objects.filter(original_customer_id=customer.id).first()
            if not existing_history:
                # Create CustomerHistory record for fully paid customer
                CustomerHistory.objects.create(
                    original_customer_id=customer.id,
                    customers_name=customer.customers_name,
                    address=customer.address,
                    contact=customer.contact,
                    date_delivered=customer.date_delivered or timezone.now().date(),
                    completion_date=timezone.now().date(),
                    total_amount=customer.amount,  # Contract Amount (Gross Price)
                    total_payments=total_paid,  # Total amount actually paid
                    final_status='fully_paid',
                    item_name=customer.item,
                    item_model=extract_item_model(customer.item),
                    transaction_number=transaction_number,  # Last payment transaction number
                    completed_by=request_user,
                    term=customer.term
                )
                
                # Update customer status to fully_paid (removes from active list)
                customer.status = 'fully_paid'
                customer.completion_date = timezone.now().date()
                customer.save()
                
                # Log activity
                UserActivityLog.objects.create(
                    user=request_user,
                    action='Customer Fully Paid',
                    model_name='Customer',
                    object_id=customer.id,
                    description=f'Customer {customer.customers_name} automatically moved to Customer History - Fully Paid',
                    ip_address=get_client_ip(request_user) if hasattr(request_user, 'META') else '127.0.0.1'
                )
                
                return True  # Customer was moved
        
        return False  # Customer not fully paid yet
        
    except Exception as e:
        # Log error but don't break the payment process
        logger = logging.getLogger(__name__)
        logger.error(f"Error checking fully paid status for customer {customer.id}: {str(e)}")
        return False

def index(request):
    """Landing page for Arjen Appliances"""
    return render(request, 'landing_page.html')

def user_login(request):
    """User login view - matches original arjensystem flow"""
    # Redirect if already logged in (like original PHP)
    if request.user.is_authenticated:
        if request.user.role == 'admin':
            return redirect('admin_dashboard')
        elif request.user.role == 'staff':
            return redirect('staff_dashboard')
        elif request.user.role == 'customer':
            return redirect('customer_dashboard')
    
    error_message = None
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        try:
            # Get user with active status (like original PHP query)
            user = CustomUser.objects.get(username=username, status='active')
            
            # Authenticate user
            auth_user = authenticate(request, username=username, password=password)
            if auth_user is not None:
                # Django login first
                login(request, auth_user)
                
                # Update last login (simplified)
                try:
                    user.last_login = timezone.now()
                    user.save(update_fields=['last_login'])
                except:
                    pass  # Don't let this break login
                
                # Log activity (simplified)
                try:
                    UserActivityLog.objects.create(
                        user=user,
                        action='login',
                        description='User logged in',
                        ip_address=get_client_ip(request)
                    )
                except:
                    pass  # Don't let this break login
                
                # Role-based redirect (exact same logic as original PHP)
                if user.role == 'admin':
                    return redirect('admin_dashboard')
                elif user.role == 'staff':
                    return redirect('staff_dashboard')
                elif user.role == 'customer':
                    return redirect('customer_dashboard')
                else:
                    return redirect('admin_dashboard')  # default fallback
            else:
                error_message = "Invalid Username and Password"
                
        except CustomUser.DoesNotExist:
            error_message = "Invalid Username and Password"
    
    return render(request, 'auth/user_login.html', {'error': error_message})

def user_logout(request):
    """User logout view"""
    if request.user.is_authenticated:
        UserActivityLog.objects.create(
            user=request.user,
            action='Logout',
            description=f'User {request.user.username} logged out',
            ip_address=get_client_ip(request)
        )
    logout(request)
    return redirect('login')

def register(request):
    """User registration view - matches original arjensystem"""
    if request.method == 'POST':
        print(f"Registration POST data: {request.POST}")  # Debug
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', '')
        
        print(f"Parsed data: username={username}, password={password}, confirm_password={confirm_password}, full_name={full_name}, email={email}, role={role}")  # Debug
        
        # Validation (exact same as original PHP)
        if not all([username, password, full_name, email, role]):
            messages.error(request, "All fields are required.")
        elif password != confirm_password:
            messages.error(request, "Passwords do not match.")
        elif len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
        elif not email or '@' not in email or '.' not in email.split('@')[-1]:
            messages.error(request, "Please enter a valid email address.")
        elif role not in ['customer', 'staff']:
            messages.error(request, "Please select a valid account type.")
        else:
            # Check if username already exists
            if CustomUser.objects.filter(username=username).exists():
                messages.error(request, "Username already exists. Please choose a different username.")
            else:
                try:
                    # Create new user (exact same logic as PHP)
                    user = CustomUser.objects.create_user(
                        username=username,
                        password=password,
                        email=email,
                        full_name=full_name,
                        role=role,
                        status='pending'  # Pending approval like original
                    )
                    messages.success(request, "Registration successful! Your account is pending approval. You will be notified once approved.")
                    # Clear form data by redirecting
                    return redirect('register')
                except Exception as e:
                    messages.error(request, "Registration failed. Please try again.")
    
    # Create a form object for template compatibility
    form = type('Form', (), {
        'username': type('Field', (), {'value': request.POST.get('username', '') if request.method == 'POST' else ''}),
        'full_name': type('Field', (), {'value': request.POST.get('full_name', '') if request.method == 'POST' else ''}),
        'email': type('Field', (), {'value': request.POST.get('email', '') if request.method == 'POST' else ''}),
        'role': type('Field', (), {'value': request.POST.get('role', '') if request.method == 'POST' else ''}),
    })()
    
    return render(request, 'auth/user_register.html', {'form': form})

@login_required
def admin_dashboard(request):
    """Admin dashboard with comprehensive analytics"""
    if request.user.role != 'admin':
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Dashboard statistics
    total_customers = Customer.objects.filter(status='active').count()
    today = date.today()
    
    # Payments due today - simplified calculation
    payments_due_today = 0
    for customer in Customer.objects.filter(status='active'):
        if customer.next_due_date == today:
            payments_due_today += 1
    
    # Today's collections
    today_payments = PaymentRecord.objects.filter(payment_date=today)
    today_collections = today_payments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    today_payment_count = today_payments.count()
    
    # This month's revenue
    month_start = today.replace(day=1)
    month_revenue = PaymentRecord.objects.filter(
        payment_date__gte=month_start,
        payment_date__lte=today
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    # Overdue customers
    overdue_customers = []
    for customer in Customer.objects.filter(status='active'):
        if customer.is_overdue:
            overdue_customers.append(customer)
    
    # Recent activity
    recent_payments = PaymentRecord.objects.select_related('customer').order_by('-created_at')[:10]
    recent_customers = Customer.objects.order_by('-created_at')[:5]
    
    context = {
        'total_customers': total_customers,
        'payments_due_today': payments_due_today,
        'today_collections': today_collections,
        'today_payment_count': today_payment_count,
        'month_revenue': month_revenue,
        'overdue_count': len(overdue_customers),
        'overdue_customers': overdue_customers[:10],
        'recent_payments': recent_payments,
        'recent_customers': recent_customers,
    }
    
    return render(request, 'dashboard/admin_main_dashboard.html', context)

@login_required
def staff_dashboard(request):
    """Staff dashboard focused on collections - matches staff_dashboard.php exactly"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Log dashboard access (matching PHP)
    try:
        UserActivityLog.objects.create(
            user=request.user,
            action='view',
            description='Accessed staff dashboard',
            ip_address=get_client_ip(request)
        )
    except:
        pass  # Don't let logging break the dashboard
    
    # Get total customers (only active) - matching PHP logic
    total_customers = Customer.objects.filter(
        Q(status='active') | Q(status__isnull=True)
    ).count()
    
    # Get overdue payments count and due soon count - using same logic as PHP
    overdue_customers = []
    due_soon_count = 0
    customers = Customer.objects.filter(
        Q(status='active') | Q(status__isnull=True)
    ).exclude(date_delivered__isnull=True)
    
    for customer in customers:
        # Calculate payments made
        payments_made = PaymentRecord.objects.filter(customer=customer).count()
        total_paid = PaymentRecord.objects.filter(customer=customer).aggregate(
            total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Skip if fully paid
        if payments_made >= customer.term:
            continue
        
        # Calculate contract details
        total_contract = customer.monthly_due * customer.term
        balance = total_contract - total_paid
        
        # Calculate expected payments based on delivery date
        days_since_delivery = (date.today() - customer.date_delivered).days
        expected_payments = (days_since_delivery // 30) + 1
        overdue_payments = max(0, expected_payments - payments_made)
        
        # Calculate next due date
        next_due_date = customer.date_delivered + timedelta(days=30 * (payments_made + 1))
        days_overdue = max(0, (date.today() - next_due_date).days)
        
        # Count due soon (payments due within 7 days but not overdue)
        if overdue_payments == 0 and days_overdue <= 7 and days_overdue >= -7:
            due_soon_count += 1
        
        # Only include if there are overdue payments
        if overdue_payments > 0:
            overdue_customers.append({
                'customer': customer,
                'payments_made': payments_made,
                'expected_payments': expected_payments,
                'overdue_payments': overdue_payments,
                'next_due_date': next_due_date,
                'days_overdue': days_overdue,
                'balance': balance,
                'total_contract': total_contract,
                'total_paid': total_paid
            })
    
    # Sort by overdue payments (highest first), then by days overdue
    overdue_customers.sort(key=lambda x: (x['overdue_payments'], x['days_overdue']), reverse=True)
    overdue_count = len(overdue_customers)
    
    # Today's collections - matching PHP query
    today_payments = PaymentRecord.objects.filter(payment_date=date.today())
    today_collections = today_payments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    today_payment_count = today_payments.count()
    
    # This month's collections - matching PHP query
    current_month = date.today().month
    current_year = date.today().year
    month_payments = PaymentRecord.objects.filter(
        payment_date__month=current_month,
        payment_date__year=current_year
    )
    month_collections = month_payments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    month_payment_count = month_payments.count()
    
    # Recent payment history (match Payments page dataset)
    recent_payments = PaymentRecord.objects.select_related('customer', 'customer_item', 'recorded_by').filter(
        customer__status='active'
    ).order_by('-created_at')[:20]
    
    context = {
        'user': request.user,
        'username': request.user.full_name or request.user.username,
        'total_customers': total_customers,
        'overdue_count': overdue_count,
        'due_soon_count': due_soon_count,
        'priority_customers': overdue_customers[:10],  # Top 10 for priority section
        'recent_payments': recent_payments,
        'today_collections': today_collections,
        'today_payment_count': today_payment_count,
        'month_collections': month_collections,
        'month_payment_count': month_payment_count,
    }
    
    return render(request, 'dashboard/staff_main_dashboard.html', context)

@login_required
def customer_dashboard(request):
    """Enhanced customer dashboard - matches customer_dashboard_enhanced.php exactly"""
    if request.user.role != 'customer':
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Get customer_id from user (matching original PHP logic)
    customer_id = request.user.customer_id
    
    # Check if customer_id exists
    if not customer_id:
        context = {
            'customer': None,
        }
        return render(request, 'dashboard/customer_main_dashboard.html', context)
    
    # Get customer information
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        context = {
            'customer': None,
        }
        return render(request, 'dashboard/customer_main_dashboard.html', context)
    
    # Calculate current month payment due as the sum of monthly dues for ALL active items
    current_month = timezone.now().month
    current_year = timezone.now().year

    active_items_for_billing = CustomerItem.objects.filter(customer=customer, status='active')

    current_month_total_due = Decimal('0.00')
    for item in active_items_for_billing:
        current_month_total_due += item.monthly_due or Decimal('0.00')

    # Fallback for legacy customers without CustomerItem records
    if current_month_total_due == 0 and (customer.monthly_due or Decimal('0.00')) > 0:
        current_month_total_due = customer.monthly_due or Decimal('0.00')
    
    # Calculate monthly billing status based on payments
    monthly_status = 'pending'
    monthly_amount_paid = Decimal('0.00')
    monthly_remaining = current_month_total_due.quantize(Decimal('1'), rounding='ROUND_HALF_UP')
    
    # Check if there are payments this month
    current_month_payments = PaymentRecord.objects.filter(
        customer=customer,
        payment_date__month=current_month,
        payment_date__year=current_year
    )
    
    if current_month_payments.exists():
        monthly_amount_paid = current_month_payments.aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0.00')
        monthly_remaining = max(Decimal('0.00'), current_month_total_due - monthly_amount_paid).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
        
        if monthly_remaining <= 0:
            monthly_status = 'paid'
        elif monthly_amount_paid > 0:
            monthly_status = 'partial'
    
    monthly_billing = {
        'total_due': current_month_total_due,
        'amount_paid': monthly_amount_paid,
        'remaining_balance': monthly_remaining,
        'due_date': timezone.now().replace(day=28),  # Assuming payments due on 28th
        'status': monthly_status
    }
    
    # Get current month transaction number
    current_transaction_number = generate_transaction_number()
    
    # Get customer items from customer_items table (multiple items support)
    customer_items = CustomerItem.objects.filter(
        customer=customer, 
        status='active'
    ).order_by('-purchase_date')
    
    # Calculate contract details first (enhanced calculation logic)
    all_payments = PaymentRecord.objects.filter(customer=customer)
    
    # Calculate total paid including rebates from payment records
    payment_totals = all_payments.aggregate(
        total_payments=Sum('amount_paid'),
        total_rebates=Sum('rebate_amount')
    )
    
    total_paid = (payment_totals['total_payments'] or Decimal('0.00')) + (payment_totals['total_rebates'] or Decimal('0.00'))
    payments_made = all_payments.count()
    
    # Enhanced calculation logic
    downpayment = customer.downpayment or Decimal('0.00')
    
    # Calculate total contract amount based on available data
    if customer_items:
        # Use customer_items data if available (more accurate)
        total_contract = sum(item.total_contract_amount or Decimal('0.00') for item in customer_items)
        # Add downpayment if not already included in contract amount
        if downpayment > 0 and all(not hasattr(item, 'downpayment') or item.downpayment == 0 for item in customer_items):
            total_contract += downpayment
    else:
        # Fallback to customer table calculation
        total_contract = (customer.monthly_due * customer.term) + downpayment
    
    # Apply rebates
    total_due = total_contract - (customer.rebates or Decimal('0.00'))
    
    # Calculate remaining balance (rounded to whole numbers)
    balance = max(Decimal('0.00'), total_due - total_paid).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
    
    # Calculate payments remaining
    payments_remaining = max(0, customer.term - payments_made)
    
    # Universal payment allocation system for ALL customers
    for item in customer_items:
        # Get item-specific payments (payments linked to this specific item)
        item_payments = PaymentRecord.objects.filter(customer=customer, customer_item=item)
        item_payment_totals = item_payments.aggregate(
            total_payments=Sum('amount_paid'),
            total_rebates=Sum('rebate_amount')
        )
        
        # Calculate item-specific totals
        item_total_paid = (item_payment_totals['total_payments'] or Decimal('0.00')) + (item_payment_totals['total_rebates'] or Decimal('0.00'))
        item_payments_made = item_payments.count()
        
        # Get general payments (not linked to any specific item)
        general_payments = PaymentRecord.objects.filter(customer=customer, customer_item__isnull=True)
        general_payment_totals = general_payments.aggregate(
            total_payments=Sum('amount_paid'),
            total_rebates=Sum('rebate_amount')
        )
        
        general_total_paid = (general_payment_totals['total_payments'] or Decimal('0.00')) + (general_payment_totals['total_rebates'] or Decimal('0.00'))
        
        # Calculate item proportion for both payment allocation and rebate calculation
        item_proportion = item.total_contract_amount / total_contract if total_contract > 0 else Decimal('1.00')
        
        # For multi-item customers, distribute general payments proportionally
        if len(customer_items) > 1 and general_total_paid > 0:
            item_general_allocation = general_total_paid * item_proportion
        else:
            # Single item gets all general payments
            item_general_allocation = general_total_paid
        
        # Calculate final item totals
        item.item_specific_paid = item_total_paid
        item.general_allocation = item_general_allocation
        item.total_paid = item_total_paid + item_general_allocation
        item.payments_made = item_payments_made + general_payments.count()
        
        # Calculate item-specific remaining balance using running balance from payment records
        # Get the final running balance from the last payment record for this item
        item_last_payment = PaymentRecord.objects.filter(customer=customer, customer_item=item).order_by('payment_date', 'id').last()
        if item_last_payment and hasattr(item_last_payment, 'running_balance'):
            item.remaining_balance = item_last_payment.running_balance
        else:
            # Fallback: Contract - (Payments + Rebates)
            item_total_due = item.total_contract_amount
            item.remaining_balance = max(Decimal('0.00'), item.total_contract_amount - item.total_paid).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
        
        # Ensure contract amount is calculated correctly (not relying on potentially incorrect database values)
        calculated_contract = item.monthly_due * item.term_months if item.monthly_due and item.term_months else Decimal('0.00')
        if abs(item.total_contract_amount - calculated_contract) > Decimal('0.01'):
            # Update incorrect contract amount in database
            item.total_contract_amount = calculated_contract
            item.save()
            # Recalculate balance with correct contract
            item.remaining_balance = max(Decimal('0.00'), calculated_contract - item.total_paid).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
        
        # Calculate payment progress based on proportion of contract paid
        item.payment_progress = (item.total_paid / item_total_due * 100) if item_total_due > 0 else 0
        
        # Calculate gross price (monthly_due × term + downpayment)
        item_monthly_due = item.monthly_due or Decimal('0.00')
        item_term = item.term_months or 1
        item_downpayment = item.downpayment or Decimal('0.00')
        item.calculated_gross_price = (item_monthly_due * item_term) + item_downpayment
        
        # Determine payment status for this item
        if item.remaining_balance <= 0:
            item.payment_status = 'fully_paid'
        elif item.total_paid > 0:
            item.payment_status = 'partial'
        else:
            item.payment_status = 'unpaid'
    
    # Fallback: If no items in customer_items table, check customers table (legacy support)
    if not customer_items and customer.item:
        # Parse item details from customers table
        item_text = customer.item.strip()
        last_space_pos = item_text.rfind(' ')
        if last_space_pos != -1:
            item_name = item_text[:last_space_pos].strip()
            item_model = item_text[last_space_pos + 1:].strip()
        else:
            item_name = item_text
            item_model = 'Unknown Model'
        
        # Use the universal payment calculation for legacy items too
        downpayment = customer.downpayment or Decimal('0.00')
        total_contract = (customer.monthly_due * customer.term) + downpayment
        
        # Calculate item-specific balance for legacy customer (rounded to whole numbers)
        item_total_due = total_contract - (customer.rebates or Decimal('0.00'))
        item_remaining_balance = max(Decimal('0.00'), item_total_due - total_paid).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
        
        # Calculate payment progress
        payment_progress = (total_paid / item_total_due * 100) if item_total_due > 0 else 0
        
        # Determine payment status
        if item_remaining_balance <= 0:
            payment_status = 'fully_paid'
        elif total_paid > 0:
            payment_status = 'partial'
        else:
            payment_status = 'unpaid'
        
        # Create item object from customers table data
        legacy_item = type('LegacyCustomerItem', (), {
            'id': customer.id,
            'item_name': item_name,
            'item_model': item_model,
            'monthly_due': customer.monthly_due,
            'term_months': customer.term,
            'total_contract_amount': total_contract,
            'original_price': customer.monthly_due * customer.term,  # Cash price without downpayment
            'downpayment': downpayment,
            'purchase_date': customer.date_delivered,
            'payments_made': payments_made,  # Use the already calculated value
            'total_paid': total_paid,  # Use the already calculated value
            'remaining_balance': item_remaining_balance,  # Use calculated item balance
            'payment_progress': payment_progress,
            'payment_status': payment_status,
            'item_specific_paid': total_paid,  # For legacy, all payments are item-specific
            'general_allocation': Decimal('0.00')  # No general allocation for single legacy items
        })()
        
        customer_items = [legacy_item]

    # Recalculate overall remaining balance from per-item remaining balances so that
    # the dashboard summary matches the item-level balances and the My Items view.
    if customer_items:
        balance = sum(
            (getattr(item, 'remaining_balance', Decimal('0.00')) or Decimal('0.00'))
            for item in customer_items
        ).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
    
    
    # Calculate overdue payments
    overdue_payments = []
    delivery_date = customer.date_delivered
    current_date = timezone.now().date()
    
    if delivery_date:
        from dateutil.relativedelta import relativedelta
        months_since_delivery = (current_date.year - delivery_date.year) * 12 + (current_date.month - delivery_date.month)
        expected_payments = min(months_since_delivery + 1, customer.term)
        
        if payments_made < expected_payments and payments_made < customer.term:
            overdue_count = expected_payments - payments_made
            for i in range(1, overdue_count + 1):
                payment_number = payments_made + i
                due_date = delivery_date + relativedelta(months=payment_number)
                
                if due_date < current_date:
                    days_overdue = (current_date - due_date).days
                    overdue_payments.append({
                        'payment_number': payment_number,
                        'due_date': due_date,
                        'amount_due': customer.monthly_due,
                        'days_overdue': days_overdue
                    })
    
    # Determine if overdue
    is_overdue = len(overdue_payments) > 0
    overdue_amount = sum(payment['amount_due'] for payment in overdue_payments)
    
    # Calculate total cash price (for good as cash option)
    total_cash_price = Decimal('0.00')
    if customer_items:
        for item in customer_items:
            if hasattr(item, 'original_price') and item.original_price:
                total_cash_price += item.original_price
            else:
                # Fallback calculation
                total_cash_price += (item.monthly_due or Decimal('0.00')) * (item.term_months or 1)
    else:
        # Legacy calculation from customer table
        total_cash_price = customer.monthly_due * customer.term
    
    # Calculate average payment
    average_payment = Decimal('0.00')
    if payments_made > 0:
        average_payment = total_paid / payments_made
    
    contract_details = {
        'total_paid': total_paid,
        'total_contract': total_contract,
        'total_due': total_due,
        'balance': balance,
        'downpayment': downpayment,
        'total_months': customer.term,
        'payments_made': payments_made,
        'payments_remaining': payments_remaining,
        'total_cash_price': total_cash_price,
        'monthly_due': customer.monthly_due,
        'average_payment': average_payment,
    }
    
    # Use the already calculated current month payments
    this_month_payments = current_month_payments.order_by('-payment_date')

    # Prepare a small recent payment history list for the dashboard
    recent_payments = all_payments.order_by('-payment_date', '-id')[:5]
    
    context = {
        'customer': customer,
        'customer_items': customer_items,
        'contract_details': contract_details,
        'monthly_billing': monthly_billing,
        'current_transaction_number': current_transaction_number,
        'this_month_payments': this_month_payments,
        'recent_payments': recent_payments,
        'is_overdue': is_overdue,
        'overdue_amount': overdue_amount,
        'overdue_payments': overdue_payments,
    }
    
    return render(request, 'dashboard/customer_main_dashboard.html', context)

@login_required
def customer_transactions(request):
    """Customer transactions view - matches customer_transactions.php"""
    if request.user.role != 'customer':
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Get customer_id from user
    customer_id = request.user.customer_id
    if not customer_id:
        messages.error(request, 'Customer account not linked')
        return redirect('customer_dashboard')
    
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        messages.error(request, 'Customer not found')
        return redirect('customer_dashboard')
    
    # Get all payment records for this customer (newest first)
    payments = PaymentRecord.objects.filter(customer=customer).order_by('-payment_date', '-id')
    
    # Calculate summary data (payments and rebates)
    payment_totals = payments.aggregate(
        total_payments=Sum('amount_paid'),
        total_rebates=Sum('rebate_amount')
    )
    total_paid = payment_totals['total_payments'] or Decimal('0.00')  # For display in summary card
    total_paid_with_rebates = (payment_totals['total_payments'] or Decimal('0.00')) + \
                              (payment_totals['total_rebates'] or Decimal('0.00'))
    payment_count = payments.count()
    
    # Calculate average payment (based on amount_paid only)
    average_payment = Decimal('0.00')
    if payment_count > 0:
        average_payment = total_paid / payment_count

    # Compute overall contract and remaining balance (mirrors customer dashboard logic in simplified form)
    customer_items = CustomerItem.objects.filter(customer=customer, status='active')
    if customer_items.exists():
        total_contract = sum((item.total_contract_amount or Decimal('0.00')) for item in customer_items)
    else:
        total_contract = (customer.monthly_due or Decimal('0.00')) * (customer.term or 0)

    remaining_balance = total_contract - total_paid_with_rebates
    if remaining_balance < Decimal('0.00'):
        remaining_balance = Decimal('0.00')

    # Calculate per-item running balances so they match My Items → Payment Breakdown
    per_payment_balance = {}
    items_for_balance = CustomerItem.objects.filter(customer=customer)
    for item in items_for_balance:
        item_contract = item.total_contract_amount or Decimal('0.00')
        running_balance_item = item_contract
        item_payments = PaymentRecord.objects.filter(
            customer=customer,
            customer_item=item
        ).order_by('payment_date', 'id')

        for p in item_payments:
            total_deduction = (p.amount_paid or Decimal('0.00')) + (p.rebate_amount or Decimal('0.00'))
            running_balance_item -= total_deduction
            if running_balance_item < Decimal('0.00'):
                running_balance_item = Decimal('0.00')
            per_payment_balance[p.id] = running_balance_item

    # Also compute a global running balance for general payments (no specific item)
    running_balance_global = total_contract
    payments_chrono = PaymentRecord.objects.filter(customer=customer).order_by('payment_date', 'id')
    for p in payments_chrono:
        total_deduction = (p.amount_paid or Decimal('0.00')) + (p.rebate_amount or Decimal('0.00'))
        running_balance_global -= total_deduction
        if running_balance_global < Decimal('0.00'):
            running_balance_global = Decimal('0.00')

        # Only assign global balance for payments that don't already have an item-specific balance
        if p.id not in per_payment_balance:
            per_payment_balance[p.id] = running_balance_global

    # Attach balance-after-payment to each payment object used in the template
    for payment in payments:
        payment.item_running_balance = per_payment_balance.get(payment.id)
    
    context = {
        'customer': customer,
        'payments': payments,
        'total_paid': total_paid,
        'payment_count': payment_count,
        'average_payment': average_payment,
        'remaining_balance': remaining_balance,
    }
    
    return render(request, 'customer/transactions.html', context)

@login_required
def customer_items(request):
    """Customer items view - matches customer_items.php"""
    if request.user.role != 'customer':
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Get customer_id from user
    customer_id = request.user.customer_id
    if not customer_id:
        messages.error(request, 'Customer account not linked')
        return redirect('customer_dashboard')
    
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        messages.error(request, 'Customer not found')
        return redirect('customer_dashboard')
    
    # Get customer items from customer_items table
    customer_items = CustomerItem.objects.filter(
        customer=customer, 
        status='active'
    ).order_by('-purchase_date')
    
    # Apply the same payment calculation logic as in customer_dashboard
    all_payments = PaymentRecord.objects.filter(customer=customer)
    payment_totals = all_payments.aggregate(
        total_payments=Sum('amount_paid'),
        total_rebates=Sum('rebate_amount')
    )
    
    total_paid_all = (payment_totals['total_payments'] or Decimal('0.00')) + (payment_totals['total_rebates'] or Decimal('0.00'))
    payments_made_all = all_payments.count()
    
    # Calculate total contract for proportional distribution
    if customer_items:
        total_contract = sum(item.total_contract_amount or Decimal('0.00') for item in customer_items)
    else:
        total_contract = Decimal('0.00')
    
    # Apply payment calculations to each item
    for item in customer_items:
        # Get item-specific payments
        item_payments = PaymentRecord.objects.filter(customer=customer, customer_item=item)
        item_payment_totals = item_payments.aggregate(
            total_payments=Sum('amount_paid'),
            total_rebates=Sum('rebate_amount')
        )
        
        item_total_paid = (item_payment_totals['total_payments'] or Decimal('0.00')) + (item_payment_totals['total_rebates'] or Decimal('0.00'))
        
        # Get general payments (not linked to any specific item)
        general_payments = PaymentRecord.objects.filter(customer=customer, customer_item__isnull=True)
        general_payment_totals = general_payments.aggregate(
            total_payments=Sum('amount_paid'),
            total_rebates=Sum('rebate_amount')
        )
        
        general_total_paid = (general_payment_totals['total_payments'] or Decimal('0.00')) + (general_payment_totals['total_rebates'] or Decimal('0.00'))
        
        # Calculate item proportion for general payment allocation
        item_proportion = item.total_contract_amount / total_contract if total_contract > 0 else Decimal('1.00')
        
        # Distribute general payments proportionally
        if len(customer_items) > 1 and general_total_paid > 0:
            item_general_allocation = general_total_paid * item_proportion
        else:
            item_general_allocation = general_total_paid
        
        # Set final item payment data
        item.total_paid = item_total_paid + item_general_allocation

        # Determine how many full monthly dues have been covered for this item
        # Use the same rule as the admin/staff Payments page: only count fully covered
        # months based on total deductions (payments + rebates, including allocated general payments)
        if item.monthly_due and item.term_months:
            full_months_paid = int(item.total_paid // item.monthly_due)
            if full_months_paid > item.term_months:
                full_months_paid = item.term_months
        else:
            full_months_paid = 0

        # Store months-based counts so the customer view matches the admin view
        item.payments_made = full_months_paid
        
        # Calculate remaining balance using running balance from payment records
        # Get the final running balance from the last payment record for this item
        item_last_payment = PaymentRecord.objects.filter(customer=customer, customer_item=item).order_by('payment_date', 'id').last()
        if item_last_payment and hasattr(item_last_payment, 'running_balance'):
            item.remaining_balance = item_last_payment.running_balance
        else:
            # Fallback: Contract - (Payments + Rebates)
            item.remaining_balance = max(Decimal('0.00'), item.total_contract_amount - item.total_paid).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
        
        # Ensure contract amount is calculated correctly (not relying on potentially incorrect database values)
        calculated_contract = item.monthly_due * item.term_months if item.monthly_due and item.term_months else Decimal('0.00')
        if abs(item.total_contract_amount - calculated_contract) > Decimal('0.01'):
            # Update incorrect contract amount in database
            item.total_contract_amount = calculated_contract
            item.save()
            # Recalculate balance with correct contract
            item.remaining_balance = max(Decimal('0.00'), calculated_contract - item.total_paid).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
        
        # Calculate payment progress percentage (same as dashboard - based on payments made)
        if item.term_months and item.term_months > 0:
            item.payment_progress = (item.payments_made / item.term_months * 100)
        else:
            item.payment_progress = 0
        
        # Calculate payments remaining
        item.payments_remaining = max(0, (item.term_months or 0) - item.payments_made)
    
    # Generate payment breakdown for each item (matching admin payment history logic)
    for item in customer_items:
        # Generate payment records using the same logic as admin payment history
        payment_records = []
        start_date = item.purchase_date  # Delivery date
        
        # Get actual payments for this item
        actual_payments = PaymentRecord.objects.filter(customer=customer, customer_item=item).order_by('payment_date')
        actual_payment_index = 0
        
        running_balance = item.total_contract_amount
        
        for month in range(item.term_months):
            # Calculate due date (first payment due one month after delivery)
            from dateutil.relativedelta import relativedelta as rd
            due_date = start_date + rd(months=month + 1)
            
            # Find matching actual payment (chronologically)
            actual_payment = None
            if actual_payment_index < len(actual_payments):
                actual_payment = actual_payments[actual_payment_index]
                actual_payment_index += 1
            
            # Create payment record
            if actual_payment:
                # Use actual payment data
                payment_amount = actual_payment.amount_paid
                rebate_amount = actual_payment.rebate_amount or Decimal('0.00')
                total_deduction = payment_amount + rebate_amount
                running_balance -= total_deduction
                
                payment_record = {
                    'transaction_number': actual_payment.transaction_number or f'TXN-{due_date.strftime("%Y-%m")}-{month+1:03d}',
                    'due_date': due_date,
                    'payment_date': actual_payment.payment_date,
                    'amount_paid': payment_amount,
                    'payment_method': actual_payment.payment_method or 'Cash',
                    'rebate_amount': rebate_amount,
                    'running_balance': max(Decimal('0.00'), running_balance),
                    'notes': actual_payment.notes or '',
                    'status': 'PAID',
                    'created_at': actual_payment.created_at,
                }
            else:
                # Generate unpaid payment slot; determine if it is overdue or just pending
                today = timezone.now().date()
                # due_date is already a date object, so compare it directly
                is_overdue = due_date < today
                payment_status = 'OVERDUE' if is_overdue else 'PENDING'

                payment_record = {
                    'transaction_number': f'TXN-{due_date.strftime("%Y-%m")}-{month+1:03d}',
                    'due_date': due_date,
                    'payment_date': None,
                    'amount_paid': Decimal('0.00'),
                    'payment_method': 'Cash',
                    'rebate_amount': Decimal('0.00'),
                    'running_balance': running_balance,
                    'notes': '',
                    'status': payment_status,
                    'created_at': None,
                }
            
            payment_records.append(payment_record)
        
        # Attach payment records to item
        item.payment_records = payment_records

        # Decide if a Remaining Balance summary row should be shown for this item.
        # Rule: show ONLY when there is at least one payment AND the last payment
        # (amount + rebate) is strictly less than the monthly due (partial last payment).
        # Apply a tiny tolerance to avoid floating/rounding artifacts.
        show_remaining_row = False
        if item.monthly_due and getattr(item, 'remaining_balance', None) and item.remaining_balance > 0:
            # Ensure we fetch the true last payment chronologically with a stable tie-breaker
            last_payment = (
                PaymentRecord.objects
                .filter(customer=customer, customer_item=item)
                .order_by('payment_date', 'id')
                .last()
            )

            if last_payment is not None:
                last_deduction = (last_payment.amount_paid or Decimal('0.00')) + (last_payment.rebate_amount or Decimal('0.00'))
                tolerance = Decimal('0.01')
                # Only show when there was a positive payment AND it was partial
                if last_deduction > Decimal('0.00') and (last_deduction + tolerance) < (item.monthly_due or Decimal('0.00')):
                    show_remaining_row = True

        # Expose flag to template
        item.show_remaining_row = show_remaining_row

    # If no items in customer_items table, create from customers table data
    if not customer_items and customer.item:
        # Parse item details from customers table
        item_text = customer.item.strip()
        last_space_pos = item_text.rfind(' ')
        if last_space_pos != -1:
            item_name = item_text[:last_space_pos].strip()
            item_model = item_text[last_space_pos + 1:].strip()
        else:
            item_name = item_text
            item_model = 'Standard Model'
        
        # Use the same payment calculation logic for legacy customers
        downpayment = customer.downpayment or Decimal('0.00')
        total_contract = (customer.monthly_due * customer.term) + downpayment
        
        # Calculate item-specific balance for legacy customer (same as admin: Contract - (Payments + Rebates))
        # Don't subtract rebates from contract, they're included in total_paid_all calculation
        remaining_balance = max(Decimal('0.00'), total_contract - total_paid_all).quantize(Decimal('1'), rounding='ROUND_HALF_UP')
        
        # Calculate progress percentage and payments remaining (same as dashboard - based on payments made)
        progress_percentage = 0
        if customer.term and customer.term > 0:
            progress_percentage = (payments_made_all / customer.term) * 100
        
        payments_remaining_legacy = max(0, customer.term - payments_made_all)
        
        from dateutil.relativedelta import relativedelta
        
        # Create legacy item object
        legacy_item = type('LegacyCustomerItem', (), {
            'id': customer.id,
            'item_name': item_name,
            'item_model': item_model,
            'monthly_due': customer.monthly_due,
            'term_months': customer.term,
            'total_contract_amount': total_contract,
            'original_price': customer.monthly_due * customer.term,
            'downpayment': downpayment,
            'purchase_date': customer.date_delivered,
            'contract_start_date': customer.date_delivered,
            'contract_end_date': customer.date_delivered + relativedelta(months=customer.term) if customer.date_delivered else None,
            'status': 'active',
            'payments_made': payments_made_all,
            'total_paid': total_paid_all,
            'remaining_balance': remaining_balance,
            'progress_percentage': progress_percentage,
            'payment_progress': progress_percentage,
            'payments_remaining': payments_remaining_legacy
        })()
        
        customer_items = [legacy_item]
    
    # Calculate summary totals
    total_contract_value = Decimal('0.00')
    total_payments_made = 0
    total_remaining_balance = Decimal('0.00')
    total_paid = Decimal('0.00')
    total_term_months = 0
    
    for item in customer_items:
        if hasattr(item, 'total_contract_amount'):
            total_contract_value += item.total_contract_amount or Decimal('0.00')
        if hasattr(item, 'payments_made'):
            total_payments_made += item.payments_made or 0
        if hasattr(item, 'remaining_balance'):
            total_remaining_balance += item.remaining_balance or Decimal('0.00')
        if hasattr(item, 'total_paid'):
            total_paid += item.total_paid or Decimal('0.00')
        if hasattr(item, 'term_months'):
            total_term_months += item.term_months or 0
    
    # Calculate additional metrics (same as dashboard - based on payments made)
    payments_remaining = max(0, total_term_months - total_payments_made)
    payment_percentage = (total_payments_made / total_term_months * 100) if total_term_months > 0 else 0
    
    # Generate payment breakdown with proper due dates (same as admin view)
    from dateutil.relativedelta import relativedelta
    from datetime import datetime
    import calendar
    
    # Get actual payment records
    actual_payments = PaymentRecord.objects.filter(customer=customer).order_by('payment_date')
    
    # Generate payment schedule with due dates
    payment_records = []
    
    # Determine start date for payment schedule
    if customer_items:
        # Use the earliest item delivery date
        start_date = min(item.purchase_date for item in customer_items if item.purchase_date)
    else:
        # Use customer delivery date
        start_date = customer.date_delivered
    
    if not start_date:
        start_date = datetime.now().date()
    
    # Generate payment schedule for total term (use EXACT same logic as admin)
    if customer_items:
        # Admin uses the FIRST ITEM's contract (monthly_due * term_months)
        first_item = customer_items[0]
        admin_total_contract = first_item.monthly_due * first_item.term_months
        admin_term = first_item.term_months
    else:
        # For legacy customers, admin uses customer monthly_due * term
        admin_total_contract = customer.monthly_due * customer.term
        admin_term = customer.term
    
    running_balance = admin_total_contract
    actual_payment_index = 0
    
    for month in range(admin_term):
        # Calculate due date (first payment due one month after delivery)
        due_date = start_date + relativedelta(months=month + 1)
        
        # Find matching actual payment (chronologically)
        actual_payment = None
        if actual_payment_index < len(actual_payments):
            actual_payment = actual_payments[actual_payment_index]
            actual_payment_index += 1
        
        # Create payment record
        if actual_payment:
            # Use actual payment data
            payment_amount = actual_payment.amount_paid
            rebate_amount = actual_payment.rebate_amount or Decimal('0.00')
            total_deduction = payment_amount + rebate_amount
            running_balance -= total_deduction
            
            payment_record = type('PaymentRecord', (), {
                'transaction_number': actual_payment.transaction_number or f'TXN-{due_date.strftime("%Y-%m")}-{month+1:03d}',
                'due_date': due_date,
                'payment_date': actual_payment.payment_date,
                'amount_paid': payment_amount,
                'payment_method': actual_payment.payment_method or 'Cash',
                'rebate_amount': rebate_amount,
                'running_balance': max(Decimal('0.00'), running_balance),
                'notes': actual_payment.notes or '',
                'customer_item': actual_payment.customer_item
            })()
        else:
            # Generate pending payment (NOT YET PAID - amount should be 0)
            payment_record = type('PaymentRecord', (), {
                'transaction_number': f'TXN-{due_date.strftime("%Y-%m")}-{month+1:03d}',
                'due_date': due_date,
                'payment_date': None,
                'amount_paid': Decimal('0.00'),  # NOT PAID YET - show 0
                'payment_method': 'Cash',
                'rebate_amount': Decimal('0.00'),
                'running_balance': running_balance,  # Balance doesn't change for unpaid
                'notes': '',
                'customer_item': None
            })()
        
        payment_records.append(payment_record)

    # Calculate admin-style summary (same as admin payment history)
    all_payments = PaymentRecord.objects.filter(customer=customer)
    admin_total_paid = sum(payment.amount_paid for payment in all_payments)
    admin_total_paid_with_rebates = sum(payment.amount_paid + (payment.rebate_amount or Decimal('0.00')) for payment in all_payments)
    
    # Use same logic as admin for contract and balance
    if customer_items:
        # Admin uses the FIRST ITEM's contract
        first_item = customer_items[0]
        admin_contract = first_item.monthly_due * first_item.term_months
        admin_actual_term = first_item.term_months
    else:
        # For legacy customers
        admin_contract = customer.monthly_due * customer.term
        admin_actual_term = customer.term
    
    # Calculate balance using running balance from payment records (like admin does)
    # The admin shows PHP 6,549 as the final balance in the payment table
    # This is the running balance after all payments and rebates
    
    # Get the final running balance from the last payment record
    last_payment = all_payments.order_by('payment_date', 'id').last()
    if last_payment and hasattr(last_payment, 'running_balance'):
        # Use the running balance from the last payment record
        admin_balance = last_payment.running_balance
    else:
        # Fallback to calculation: Contract - (Payments + Rebates)
        admin_balance = admin_contract - admin_total_paid_with_rebates
    
    # Ensure all customer items use correct calculated contract amounts
    # Fix any contract amount discrepancies in the database
    for item in customer_items:
        calculated_contract = item.monthly_due * item.term_months if item.monthly_due and item.term_months else Decimal('0.00')
        if abs(item.total_contract_amount - calculated_contract) > Decimal('0.01'):
            item.total_contract_amount = calculated_contract
            item.save()
    
    # Recalculate admin contract with corrected values
    if customer_items:
        first_item = customer_items[0]
        admin_contract = first_item.monthly_due * first_item.term_months
    
    # Recalculate balance with corrected contract
    admin_balance = admin_contract - admin_total_paid_with_rebates

    # Calculate 'payments made' based on fully covered monthly dues (same logic as customer_payments)
    admin_payments_made = 0
    term_for_summary = admin_actual_term

    # Determine the monthly due used for the overall summary
    if customer_items:
        summary_monthly_due = customer_items[0].monthly_due
    else:
        summary_monthly_due = customer.monthly_due

    if summary_monthly_due and term_for_summary:
        # Ensure we work with Decimals for safe division
        if isinstance(admin_total_paid_with_rebates, Decimal):
            total_deductions_for_months = admin_total_paid_with_rebates
        else:
            total_deductions_for_months = Decimal(str(admin_total_paid_with_rebates))

        full_months_paid = int(total_deductions_for_months // summary_monthly_due)
        if full_months_paid > term_for_summary:
            full_months_paid = term_for_summary
        admin_payments_made = full_months_paid

    admin_payments_remaining = max(0, term_for_summary - admin_payments_made)
    admin_progress_percentage = (admin_payments_made / term_for_summary * 100) if term_for_summary > 0 else 0

    context = {
        'customer': customer,
        'customer_items': customer_items,
        'total_contract_value': admin_contract,  # Use admin contract
        'total_payments_made': admin_payments_made,  # Use admin count
        # Use the sum of per-item remaining balances for the customer summary.
        'total_remaining_balance': total_remaining_balance,
        'total_paid': admin_total_paid_with_rebates,  # Use admin total with rebates
        'total_term_months': admin_actual_term,  # Use admin term
        'payments_remaining': admin_payments_remaining,  # Use admin remaining
        'payment_percentage': admin_progress_percentage,  # Use admin percentage
        'payment_records': payment_records,
        # Add admin-style variables for template compatibility
        'balance': admin_balance,
        'total_contract': admin_contract,
        'payments_made': admin_payments_made,
        'actual_term': admin_actual_term,
        'progress_percentage': admin_progress_percentage,
    }
    
    return render(request, 'customer/items.html', context)

@login_required
def monthly_statements(request):
    """Monthly statements view - matches monthly_statements.php exactly"""
    if request.user.role != 'customer':
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Get customer_id from user (matching PHP logic)
    customer_id = request.user.customer_id
    if not customer_id:
        return redirect('customer_dashboard')
    
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return redirect('customer_dashboard')
    
    monthly_statements = []
    
    # Check if monthly_statements table exists (matching PHP table check)
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='myapp_monthlystatement'")
        table_exists = cursor.fetchone()
    
    if table_exists:
        # Get from monthly_statements table if it exists
        statements = MonthlyStatement.objects.filter(customer=customer) \
            .order_by('-statement_date')[:12]
        
        for statement in statements:
            monthly_statements.append({
                'statement_month': statement.statement_date.month,
                'statement_year': statement.statement_date.year,
                'month_name': statement.statement_date.strftime('%B'),
                'total_due': statement.amount_due,
                'amount_paid': statement.amount_paid,
                'remaining_balance': statement.balance,
                'due_date': statement.due_date,
                'status': statement.status,
                'transaction_number': f"TXN-{statement.statement_date.year}-{statement.statement_date.month:02d}-0001"
            })
    
    # If no monthly statements table or no data, generate from payment_records (matching PHP logic)
    if not monthly_statements:
        # Get months that have actual transactions or payments
        from django.db.models.functions import TruncMonth, Extract
        months_with_payments = PaymentRecord.objects.filter(customer=customer) \
            .annotate(
                year=Extract('payment_date', lookup_name='year'),
                month=Extract('payment_date', lookup_name='month')
            ) \
            .values('year', 'month') \
            .distinct() \
            .order_by('-year', '-month')[:12]
        
        for month_data in months_with_payments:
            month = month_data['month']
            year = month_data['year']
            
            # Use calculateMonthlyBilling for accurate data (matching PHP)
            billing = calculate_monthly_billing(customer, month, year)
            
            # Get transaction number for this month
            month_payments = PaymentRecord.objects.filter(
                customer=customer,
                payment_date__month=month,
                payment_date__year=year
            ).exclude(transaction_number__isnull=True).order_by('-payment_date')
            
            transaction_number = f"TXN-{year}-{month:02d}-0001"
            if month_payments.exists():
                transaction_number = month_payments.first().transaction_number or transaction_number
            
            monthly_statements.append({
                'statement_month': month,
                'statement_year': year,
                'month_name': billing['due_date'].strftime('%B'),
                'total_due': billing['total_due'],
                'amount_paid': billing['amount_paid'],
                'remaining_balance': billing['remaining_balance'],
                'due_date': billing['due_date'],
                'status': billing['status'],
                'transaction_number': transaction_number
            })
        
        # If still no data, show current month only (matching PHP fallback)
        if not monthly_statements:
            current_month = timezone.now().month
            current_year = timezone.now().year
            billing = calculate_monthly_billing(customer, current_month, current_year)
            
            monthly_statements.append({
                'statement_month': current_month,
                'statement_year': current_year,
                'month_name': timezone.now().strftime('%B'),
                'total_due': billing['total_due'],
                'amount_paid': billing['amount_paid'],
                'remaining_balance': billing['remaining_balance'],
                'due_date': billing['due_date'],
                'status': billing['status'],
                'transaction_number': generate_transaction_number()
            })
    
    # Log activity (matching PHP)
    UserActivityLog.objects.create(
        user=request.user,
        action='view',
        description='Viewed monthly statements',
        ip_address=get_client_ip(request)
    )
    
    # Calculate summary statistics
    total_statements = len(monthly_statements)
    paid_statements = sum(1 for stmt in monthly_statements if stmt.get('status') == 'paid')
    pending_statements = sum(1 for stmt in monthly_statements if stmt.get('status') in ['pending', 'overdue'])
    
    context = {
        'customer': customer,
        'monthly_statements': monthly_statements,
        'total_statements': total_statements,
        'paid_statements': paid_statements,
        'pending_statements': pending_statements,
    }
    
    return render(request, 'customer/statements.html', context)

@login_required
def customers_list(request):
    """Customer management list - matches original arjensystem exactly"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Handle customer removal (matches original PHP logic)
    if request.method == 'POST' and 'remove_customer' in request.POST and request.user.role == 'admin':
        customer_id = request.POST.get('customer_id')
        removal_type = request.POST.get('removal_type')
        removal_reason = request.POST.get('removal_reason', '')
        
        try:
            customer = Customer.objects.get(id=customer_id)
            
            if removal_type == 'pullout':
                # Pull out - move to history (matches original PHP)
                # Calculate total amount paid
                total_paid = PaymentRecord.objects.filter(customer=customer).aggregate(
                    total=Sum('amount_paid')
                )['total'] or Decimal('0.00')
                
                # Create customer history record
                total_contract = customer.monthly_due * customer.term
                CustomerHistory.objects.create(
                    original_customer_id=customer.id,
                    customers_name=customer.customers_name,
                    address=customer.address,
                    contact=customer.contact,
                    date_delivered=customer.date_delivered,
                    completion_date=date.today(),
                    total_amount=total_contract,
                    total_payments=total_paid,
                    final_status='pulled_out',
                    item_name=customer.item,
                    item_model=extract_item_model(customer.item),
                    transaction_number=f'PULLOUT-{date.today().strftime("%Y%m%d")}-{customer.id:04d}',
                    completed_by=request.user,
                    term=customer.term
                )
                
                # Update customer status instead of deleting
                customer.status = 'pulled_out'
                customer.completion_date = date.today()
                customer.save()
                
                messages.success(request, f'Customer item pulled out and moved to history successfully!')
                
            elif removal_type == 'permanent':
                # Permanent delete - remove completely (matches original PHP)
                customer_name = customer.customers_name
                customer.delete()
                
                messages.success(request, 'Customer permanently deleted!')
                
        except Customer.DoesNotExist:
            messages.error(request, 'Customer not found.')
        except Exception as e:
            messages.error(request, f'Error removing customer: {str(e)}')
            
        return redirect('customers_list')
    
    # Handle add customer form submission (matches original PHP logic)
    if request.method == 'POST' and request.user.role in ['admin', 'staff']:
        print(f"=== POST request received for customer creation ===")  # Debug
        print(f"User: {request.user.username}, Role: {request.user.role}")  # Debug
        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        print(f"Is AJAX request: {is_ajax}")  # Debug
        
        # Get form data with validation
        customers_name = request.POST.get('customers_name', '').strip()
        address = request.POST.get('address', '').strip()
        contact = request.POST.get('contact', '').strip()
        date_delivered = request.POST.get('date_delivered', '').strip()
        
        # Validate required fields
        if not all([customers_name, address, contact, date_delivered]):
            error_message = "All required fields must be filled"
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })
            else:
                messages.error(request, error_message)
                return redirect('customers_list')
        
        try:
            term = int(request.POST.get('term', 0))
            rebates = Decimal(request.POST.get('rebates', '0'))
            monthly_due = Decimal(request.POST.get('monthly_due', '0'))
            original_price = Decimal(request.POST.get('original_price', '0'))
            downpayment = Decimal(request.POST.get('downpayment', '0'))
        except (ValueError, TypeError) as e:
            error_message = f"Invalid numeric values in form: {str(e)}"
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })
            else:
                messages.error(request, error_message)
                return redirect('customers_list')
        
        print(f"Form data: name={customers_name}, address={address}, contact={contact}")  # Debug
        
        # Get item fields
        item_name = request.POST.get('item_name', '').strip()
        item_model = request.POST.get('item_model', '').strip()
        
        # Create combined item field for legacy compatibility
        item = f"{item_name} {item_model}"
        
        try:
            # Calculate total contract amount (matches original PHP exactly)
            total_contract_amount = (monthly_due * term) + downpayment
            
            # Insert into customers table (matches original PHP exactly)
            customer = Customer.objects.create(
                customers_name=customers_name,
                address=address,
                contact=contact,
                date_delivered=date_delivered,
                item=item,
                term=term,
                rebates=rebates,
                monthly_due=monthly_due,
                monthly=monthly_due,  # Set monthly field to match monthly_due
                amount=total_contract_amount,  # Set total contract amount
                downpayment=downpayment,
                status='active'
            )
            
            # Calculate contract details (matches original PHP)
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            
            date_delivered_obj = datetime.strptime(date_delivered, '%Y-%m-%d').date()
            contract_start_date = date_delivered_obj
            contract_end_date = date_delivered_obj + relativedelta(months=term)
            first_due_date = date_delivered_obj + relativedelta(months=1)
            
            # Insert into customer_items table (matches original PHP exactly)
            try:
                from .models import CustomerItem
                print(f"Attempting to create CustomerItem with customer_id: {customer.id}")
                
                customer_item = CustomerItem.objects.create(
                    customer=customer,
                    item_name=item_name or '',
                    item_model=item_model or '',
                    item_description='',  # Default empty description
                    item_price=original_price,  # Set item_price to original_price
                    quantity=1,  # Set default quantity
                    original_price=original_price,
                    downpayment=downpayment,
                    good_as_cash='no',  # Add missing required field
                    rebate_amount=rebates,  # Add missing required field
                    monthly_due=monthly_due,
                    term_months=term,
                    total_contract_amount=total_contract_amount,
                    purchase_date=date_delivered_obj,
                    contract_start_date=contract_start_date,
                    contract_end_date=contract_end_date,
                    first_due_date=first_due_date,
                    status='active'
                )
                print(f"CustomerItem created successfully with ID: {customer_item.id}")
                success_message = f'Customer added successfully with detailed item information!'
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"CustomerItem creation failed: {str(e)}")
                print(f"Full error: {error_details}")
                success_message = f'Customer added successfully! (Note: Detailed item tracking not available)'
            
            # Return JSON response for AJAX requests
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({
                    'success': True,
                    'message': success_message
                })
            else:
                messages.success(request, success_message)
                return redirect('customers_list')
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Customer creation error: {error_details}")  # Debug logging
            error_message = f'Error adding customer: {str(e)}'
            # Return JSON response for AJAX requests
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })
            else:
                messages.error(request, error_message)
    
    # Get customers with their items - matches original arjensystem GROUP_CONCAT logic
    from django.db.models import Max
    from .models import CustomerItem
    
    search_query = request.GET.get('search', '').strip()
    
    # Build base queryset with annotations (equivalent to GROUP_CONCAT)
    customers_query = Customer.objects.filter(status='active').annotate(
        # Count of items per customer
        item_count=Count('items', filter=Q(items__status='active')),
        # Sum of monthly dues from all items
        total_monthly_due=Sum('items__monthly_due', filter=Q(items__status='active')),
        # Sum of total contract amounts from all items
        total_contract_value=Sum('items__total_contract_amount', filter=Q(items__status='active')),
        # Latest purchase date
        latest_purchase=Max('items__purchase_date', filter=Q(items__status='active'))
    ).prefetch_related('items')
    
    # Search functionality (enhanced to include items and models like original PHP)
    if search_query:
        customers_query = customers_query.filter(
            Q(customers_name__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(contact__icontains=search_query) |
            Q(item__icontains=search_query) |
            Q(items__item_name__icontains=search_query) |
            Q(items__item_model__icontains=search_query)
        ).distinct()
    
    customers_query = customers_query.order_by('-created_at')
    
    # Process customers to add item details (equivalent to GROUP_CONCAT)
    customers_with_items = []
    for customer in customers_query:
        # Get active items for this customer
        active_items = customer.items.filter(status='active').order_by('-purchase_date')
        
        # Add active items to customer object for template access
        customer.active_items = active_items
        
        # Create item strings (equivalent to GROUP_CONCAT) for backward compatibility
        all_items = ', '.join([item.item_name for item in active_items])
        all_models = ', '.join([item.item_model for item in active_items])
        all_prices = ', '.join([str(item.original_price) for item in active_items])
        all_monthly_due = ', '.join([str(item.monthly_due) for item in active_items])
        all_terms = ', '.join([str(item.term_months) for item in active_items])
        all_totals = ', '.join([str(item.total_contract_amount) for item in active_items])
        
        # Add calculated fields to customer object
        customer.all_items = all_items or customer.item or 'No items'
        customer.all_models = all_models or 'N/A'
        customer.all_prices = all_prices or 'N/A'  # Use N/A since Customer model doesn't have original_price
        customer.all_monthly_due = all_monthly_due or str(customer.monthly_due or 0)
        customer.all_terms = all_terms or str(customer.term or 0)
        customer.all_totals = all_totals or str((customer.monthly_due or 0) * (customer.term or 0))
        
        # Use annotated values or fallback to customer fields
        customer.calculated_total_monthly_due = customer.total_monthly_due or customer.monthly_due or 0
        
        # Gross Price Formula: (Term × Monthly Payment) + Downpayment
        monthly_payment = customer.monthly_due or 0
        term = customer.term or 0
        downpayment = customer.downpayment or 0
        customer.calculated_gross_price = (term * monthly_payment) + downpayment
        
        customers_with_items.append(customer)
    
    context = {
        'customers': customers_with_items,
        'search_query': search_query,
        'search_results_count': len(customers_with_items) if search_query else None,
    }
    
    return render(request, 'customers/customers_list.html', context)

@login_required
def add_item_modal_content(request):
    """Add item to customer modal content - matches original arjensystem exactly"""
    if request.user.role not in ['admin', 'staff']:
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get customers with item counts (max 3 items per customer)
    from .models import CustomerItem
    customers = []
    for customer in Customer.objects.filter(status='active').order_by('customers_name'):
        # Count current active items
        current_items = CustomerItem.objects.filter(customer=customer, status='active').count()
        customers.append({
            'id': customer.id,
            'customers_name': customer.customers_name,
            'address': customer.address,
            'contact': customer.contact,
            'current_items': current_items
        })
        
    if request.method == 'POST':
            
        try:
            customer_id = request.POST.get('customer_id')
            item_name = request.POST.get('item_name', '').strip()
            item_model = request.POST.get('item_model', '').strip()
            original_price = Decimal(request.POST.get('original_price', '0'))
            downpayment = Decimal(request.POST.get('downpayment', '0'))
            good_as_cash = request.POST.get('good_as_cash', '')
            rebate_amount = Decimal(request.POST.get('rebate_amount', '0'))
            monthly_due = Decimal(request.POST.get('monthly_due', '0'))
            term_months = int(request.POST.get('term_months', '0'))
            purchase_date = request.POST.get('purchase_date')
                
        except (ValueError, TypeError, InvalidOperation) as e:
            return JsonResponse({'success': False, 'message': f'Invalid input data: {str(e)}'})
            
        # Enhanced validation
        if not customer_id:
            return JsonResponse({'success': False, 'message': 'Please select a customer.'})
        if not item_name or not item_name.strip():
            return JsonResponse({'success': False, 'message': 'Please enter item name.'})
        if not item_model or not item_model.strip():
            return JsonResponse({'success': False, 'message': 'Please enter item model.'})
        if not good_as_cash:
            return JsonResponse({'success': False, 'message': 'Please select Good as Cash option.'})
        if not purchase_date:
            return JsonResponse({'success': False, 'message': 'Please select purchase date.'})
        
        # Validate numeric fields
        if original_price < 0:
            return JsonResponse({'success': False, 'message': 'Original price cannot be negative.'})
        if downpayment < 0:
            return JsonResponse({'success': False, 'message': 'Downpayment cannot be negative.'})
        if rebate_amount < 0:
            return JsonResponse({'success': False, 'message': 'Rebate amount cannot be negative.'})
        if good_as_cash == 'no' and monthly_due <= 0:
            return JsonResponse({'success': False, 'message': 'Monthly due must be greater than 0 for installment.'})
        if good_as_cash == 'no' and term_months <= 0:
            return JsonResponse({'success': False, 'message': 'Term months must be greater than 0 for installment.'})
        
        try:
            customer = Customer.objects.get(id=customer_id)
            
            # Check if customer already has 3 items (business rule limit)
            current_count = CustomerItem.objects.filter(customer=customer, status='active').count()
            if current_count >= 3:
                return JsonResponse({'success': False, 'message': 'Customer has reached the maximum limit of 3 items. Please contact admin if you need to add more items.'})
            
            # Calculate total contract amount (exact PHP logic)
            if good_as_cash == 'yes':
                total_contract_amount = original_price - rebate_amount
            else:
                total_contract_amount = (monthly_due * term_months) + downpayment - rebate_amount
            
            # Convert purchase date and calculate contract dates (matching PHP logic)
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            
            purchase_date_obj = datetime.strptime(purchase_date, '%Y-%m-%d').date()
            contract_start_date = purchase_date_obj
            contract_end_date = purchase_date_obj + relativedelta(months=term_months)
            first_due_date = purchase_date_obj + relativedelta(months=1)
            
            # Create customer item with all required fields
            customer_item = CustomerItem.objects.create(
                customer=customer,
                item_name=item_name,
                item_model=item_model,
                original_price=original_price,
                downpayment=downpayment,
                good_as_cash=good_as_cash,
                rebate_amount=rebate_amount,
                monthly_due=monthly_due,
                term_months=term_months,
                total_contract_amount=total_contract_amount,
                purchase_date=purchase_date_obj,
                contract_start_date=contract_start_date,
                contract_end_date=contract_end_date,
                first_due_date=first_due_date,
                status='active'
            )
            
            # Log activity
            UserActivityLog.objects.create(
                user=request.user,
                action='Add Item to Customer',
                model_name='CustomerItem',
                object_id=customer_item.id,
                description=f'Added {item_name} {item_model} to {customer.customers_name}',
                ip_address=get_client_ip(request)
            )
            
            # Create message exactly like PHP
            payment_type = " (Good as Cash)" if good_as_cash == 'yes' else (f" (Installment with PHP {rebate_amount:,.2f} rebate)" if rebate_amount > 0 else " (Installment)")
            total_amount = f"{total_contract_amount:,.2f}"
            message = f"✅ New item '{item_name} {item_model}' added to {customer.customers_name}'s account{payment_type}! Total contract: PHP {total_amount}. Customer's payment overview has been updated with this additional item."
            
            return JsonResponse({'success': True, 'message': message})
            
        except Customer.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Customer not found.'})
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return JsonResponse({'success': False, 'message': f'Error adding item: {str(e)}'})
    
    # Return modal HTML content for GET requests
    from datetime import date
    return render(request, 'modals/add_item_modal_content.html', {
        'customers': customers,
        'today': date.today().strftime('%Y-%m-%d')
    })

@login_required
def edit_item_modal_content(request, item_id):
    """Edit item modal content and processing"""
    if request.user.role not in ['admin', 'staff']:
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    try:
        item = CustomerItem.objects.get(id=item_id)
    except CustomerItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Item not found'})
    
    if request.method == 'POST':
        try:
            # Get form data
            item_name = request.POST.get('item_name', '').strip()
            item_model = request.POST.get('item_model', '').strip()
            original_price = Decimal(request.POST.get('original_price', '0'))
            downpayment = Decimal(request.POST.get('downpayment', '0'))
            good_as_cash = request.POST.get('good_as_cash', '')
            rebate_amount = Decimal(request.POST.get('rebate_amount', '0'))
            monthly_due = Decimal(request.POST.get('monthly_due', '0'))
            term_months = int(request.POST.get('term_months', '0'))
            purchase_date = request.POST.get('purchase_date')
            
        except (ValueError, TypeError, InvalidOperation) as e:
            return JsonResponse({'success': False, 'message': f'Invalid input data: {str(e)}'})
        
        # Validation
        if not item_name or not item_name.strip():
            return JsonResponse({'success': False, 'message': 'Please enter item name.'})
        if not item_model or not item_model.strip():
            return JsonResponse({'success': False, 'message': 'Please enter item model.'})
        if not good_as_cash:
            return JsonResponse({'success': False, 'message': 'Please select Good as Cash option.'})
        if not purchase_date:
            return JsonResponse({'success': False, 'message': 'Please select purchase date.'})
        
        try:
            # Calculate total contract amount (exact PHP logic)
            if good_as_cash == 'yes':
                total_contract_amount = original_price - rebate_amount
            else:
                total_contract_amount = (monthly_due * term_months) + downpayment - rebate_amount
            
            # Convert purchase date and calculate contract dates
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            
            purchase_date_obj = datetime.strptime(purchase_date, '%Y-%m-%d').date()
            contract_start_date = purchase_date_obj
            contract_end_date = purchase_date_obj + relativedelta(months=term_months)
            first_due_date = purchase_date_obj + relativedelta(months=1)
            
            # Update item
            item.item_name = item_name
            item.item_model = item_model
            item.original_price = original_price
            item.downpayment = downpayment
            item.good_as_cash = good_as_cash
            item.rebate_amount = rebate_amount
            item.monthly_due = monthly_due
            item.term_months = term_months
            item.total_contract_amount = total_contract_amount
            item.purchase_date = purchase_date_obj
            item.contract_start_date = contract_start_date
            item.contract_end_date = contract_end_date
            item.first_due_date = first_due_date
            item.save()
            
            # Log activity
            UserActivityLog.objects.create(
                user=request.user,
                action='Edit Item',
                model_name='CustomerItem',
                object_id=item.id,
                description=f'Updated {item_name} {item_model} for {item.customer.customers_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Success message
            payment_type = " (Good as Cash)" if good_as_cash == 'yes' else ""
            total_amount = f"{total_contract_amount:,.2f}"
            message = f"✅ Item '{item_name} {item_model}' updated successfully{payment_type}! Total contract: PHP {total_amount}."
            
            return JsonResponse({'success': True, 'message': message})
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return JsonResponse({'success': False, 'message': f'Error updating item: {str(e)}'})
    
    # Return modal HTML content for GET requests
    from datetime import date
    return render(request, 'modals/edit_item_modal_content.html', {
        'item': item,
        'today': date.today().strftime('%Y-%m-%d')
    })

@login_required
def add_customer(request):
    """Add new customer"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            
            # CRITICAL FIX: Create corresponding CustomerItem record
            from datetime import date
            from dateutil.relativedelta import relativedelta
            
            # Calculate contract dates
            purchase_date = customer.date_delivered
            contract_start_date = purchase_date
            contract_end_date = purchase_date + relativedelta(months=customer.term)
            first_due_date = purchase_date + relativedelta(months=1)
            
            # Create CustomerItem record with data from Customer
            CustomerItem.objects.create(
                customer=customer,
                item_name=customer.item,
                item_model='',  # Not available in old Customer model
                item_description='',
                item_price=customer.amount,
                quantity=1,
                original_price=customer.amount,
                downpayment=customer.downpayment,
                good_as_cash='no',
                rebate_amount=customer.rebates,
                monthly_due=customer.monthly_due,
                term_months=customer.term,
                total_contract_amount=customer.amount,
                purchase_date=purchase_date,
                contract_start_date=contract_start_date,
                contract_end_date=contract_end_date,
                first_due_date=first_due_date,
                status='active'
            )
            
            print(f"DEBUG: Created CustomerItem for {customer.customers_name}: term={customer.term}, monthly_due={customer.monthly_due}")
            
            # Log activity
            UserActivityLog.objects.create(
                user=request.user,
                action='Create Customer',
                model_name='Customer',
                object_id=customer.id,
                description=f'Created customer: {customer.customers_name}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'Customer {customer.customers_name} added successfully!')
            return redirect('customers_list')
    else:
        form = CustomerForm()
    
    return render(request, 'customers/add.html', {'form': form})

@login_required
def payments(request):
    """Main payments page with tabs - matches original arjensystem"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Get payment statistics
    total_payments_data = PaymentRecord.objects.aggregate(
        count=Count('id'),
        total=Sum('amount_paid')
    )
    
    today_payments_data = PaymentRecord.objects.filter(
        payment_date=date.today()
    ).aggregate(
        count=Count('id'),
        total=Sum('amount_paid')
    )
    
    # Get recent payments for history tab
    recent_payments = PaymentRecord.objects.select_related('customer', 'customer_item', 'recorded_by').filter(
        customer__status='active'
    ).order_by('-created_at')[:20]
    
    # Handle payment recording (matching PHP logic)
    if request.method == 'POST' and 'add_payment' in request.POST:
        try:
            customer_id = request.POST.get('customer_id')
            payment_number = request.POST.get('payment_number')
            payment_date = request.POST.get('payment_date')
            amount_paid = Decimal(request.POST.get('amount_paid'))
            payment_method = request.POST.get('payment_method', 'Cash')
            rebate_applied = request.POST.get('rebate_applied', 'No')
            notes = request.POST.get('notes', '')
            
            # Require notes for every recorded payment
            if not notes or not notes.strip():
                messages.error(request, 'Notes are required for every payment. Please describe this payment in the notes field.')
                return redirect('payments')
            
            customer = Customer.objects.get(id=customer_id)
            
            # Create payment record
            PaymentRecord.objects.create(
                customer=customer,
                payment_number=payment_number,
                payment_date=payment_date,
                amount_paid=amount_paid,
                payment_method=payment_method,
                has_rebate=(rebate_applied == 'Yes'),
                notes=notes
            )
            
            # Log activity
            UserActivityLog.objects.create(
                user=request.user,
                action='create',
                description=f'Recorded payment: Customer ID {customer_id}, Payment #{payment_number}, Amount: PHP {amount_paid}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, 'Payment recorded successfully!')
            return redirect('payments')
            
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')
    
    # Handle payment deletion (admin only, matching PHP logic)
    if request.method == 'GET' and 'delete' in request.GET and request.user.role == 'admin':
        try:
            payment_id = request.GET.get('delete')
            payment = PaymentRecord.objects.get(id=payment_id)
            payment.delete()
            
            # Log activity
            UserActivityLog.objects.create(
                user=request.user,
                action='delete',
                description=f'Deleted payment record ID: {payment_id}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, 'Payment deleted successfully!')
            return redirect('payments')
            
        except Exception as e:
            messages.error(request, f'Error deleting payment: {str(e)}')
    
    # Get customers for record payment tab (only active)
    customers = Customer.objects.filter(
        Q(status='active') | Q(status__isnull=True)
    ).order_by('customers_name')
    
    # Get payment records for display (only from active customers)
    payment_records = PaymentRecord.objects.select_related('customer').filter(
        customer__status__in=['active', None]
    ).order_by('-created_at')[:50]
    
    context = {
        'total_payments_count': total_payments_data['count'] or 0,
        'total_payments_amount': total_payments_data['total'] or 0,
        'today_payments_count': today_payments_data['count'] or 0,
        'today_payments_amount': today_payments_data['total'] or 0,
        'recent_payments': recent_payments,
        'customers': customers,
        'payment_records': payment_records,
    }
    
    return render(request, 'payments/payments.html', context)

@login_required
def record_payment(request):
    """Record customer payment - matches original arjensystem"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    if request.method == 'POST':
        print(f"POST request received. POST data: {request.POST}")
        print(f"'add_payment' in POST: {'add_payment' in request.POST}")
        
        if 'add_payment' in request.POST:
            print("Processing payment form submission...")
            customer_id = request.POST.get('customer_id')
            customer_item_id = request.POST.get('customer_item_id')
            payment_date_str = request.POST.get('payment_date')
            amount_paid = request.POST.get('amount_paid')
            payment_method = request.POST.get('payment_method', 'Cash')
            rebate_applied = request.POST.get('rebate_applied', 'No')
            rebate_amount_input = request.POST.get('rebate_amount', '0')
            notes = request.POST.get('notes', '')
            
            # Convert payment_date string to date object
            from datetime import datetime
            try:
                payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                payment_date = datetime.now().date()
            
            print(f"Form data extracted: customer_id={customer_id}, payment_date={payment_date}, amount_paid={amount_paid}")
            
            # Basic validation only
            if not customer_id or not amount_paid:
                messages.error(request, 'Please fill in all required fields.')
                return redirect('record_payment')
            if not notes or not notes.strip():
                messages.error(request, 'Notes are required for every payment. Please describe this payment in the notes field.')
                return redirect('record_payment')
            try:
                customer = Customer.objects.get(id=customer_id)
                
                # Handle customer item - allow for legacy payments without item link
                customer_item = None
                if customer_item_id:
                    try:
                        customer_item = CustomerItem.objects.get(id=customer_item_id, customer=customer)
                    except CustomerItem.DoesNotExist:
                        # If item doesn't exist, create payment without item link (legacy support)
                        customer_item = None
                
                # Handle rebate amount
                rebate_amount = Decimal('0.00')
                has_rebate = rebate_applied == 'Yes'
                if has_rebate and rebate_amount_input:
                    try:
                        rebate_amount = Decimal(rebate_amount_input)
                    except (ValueError, TypeError):
                        rebate_amount = Decimal('0.00')
                
                # Create payment record with transaction number system
                print(f"Creating payment record for customer: {customer.customers_name}")
                
                # Create the payment record without payment_number and transaction_number
                # These will be auto-generated in the save method
                payment = PaymentRecord.objects.create(
                    customer=customer,
                    customer_item=customer_item,
                    payment_date=payment_date,
                    amount_paid=Decimal(amount_paid),
                    payment_method=payment_method,
                    recorded_by=request.user,
                    has_rebate=has_rebate,
                    rebate_amount=rebate_amount,
                    notes=notes
                )
                
                print(f"Payment saved successfully with ID: {payment.id}, Transaction: {payment.transaction_number}")
                
                # Update customer payment totals (this is already done in PaymentRecord.save())
                customer.refresh_from_db()
                print(f"Customer payment total updated to: PHP {customer.payments}")
                
                # Check if customer is now fully paid and move to CustomerHistory if so
                was_moved = check_and_move_fully_paid_customer(customer, request.user)
                
                # Log activity
                UserActivityLog.objects.create(
                    user=request.user,
                    action='Record Payment',
                    model_name='PaymentRecord',
                    object_id=payment.id,
                    description=f'Recorded payment: Customer {customer.customers_name}, Transaction #{payment.transaction_number}, Amount: PHP {amount_paid}',
                    ip_address=get_client_ip(request)
                )
                
                if was_moved:
                    messages.success(request, f'Payment recorded successfully! Customer {customer.customers_name} has been automatically moved to Customer History - Fully Paid.')
                else:
                    messages.success(request, 'Payment recorded successfully!')
                return redirect('payments')
                
            except Customer.DoesNotExist:
                messages.error(request, 'Customer not found.')
            except Exception as e:
                error_msg = str(e)
                print(f"Payment recording error: {error_msg}")
                # Add debugging info for development
                import traceback
                print(f"Full traceback: {traceback.format_exc()}")
                
                # Show a user-friendly message instead of the technical error
                messages.error(request, 'Payment could not be processed. Please try again.')
                
                # If it's a database constraint error, show specific message
                if 'constraint' in error_msg.lower() or 'missing' in error_msg.lower():
                    messages.error(request, 'Database validation error. Please contact administrator.')
                    print(f"Database constraint error: {error_msg}")
        else:
            print("POST request received but 'add_payment' not found in POST data")
    
    # Get customers for dropdown - only active customers
    customers = Customer.objects.filter(status='active').order_by('customers_name')
    
    return render(request, 'payments/record_payment.html', {
        'customers': customers
    })

@login_required
def due_payments_report(request):
    """Due payments report - matches original arjensystem exactly"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Get filter parameters (same as original PHP)
    filter_status = request.GET.get('status', 'all')
    
    # Get all active customers with payment calculations (same logic as original PHP)
    customers_data = []
    stats = {
        'total_customers': 0,
        'overdue_customers': 0,
        'due_soon_customers': 0,
        'current_customers': 0,
        'total_overdue_amount': 0
    }
    
    for customer in Customer.objects.filter(status='active'):
        if not customer.date_delivered or not customer.monthly_due:
            continue
            
        # Count payments made
        payments_made = PaymentRecord.objects.filter(customer=customer).count()
        total_paid = PaymentRecord.objects.filter(customer=customer).aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        
        # Calculate expected payments (same as original PHP)
        from datetime import date
        days_since_delivery = (date.today() - customer.date_delivered).days
        expected_payments = max(0, (days_since_delivery // 30) + 1)
        
        # Calculate overdue payments
        overdue_payments = max(0, expected_payments - payments_made)
        
        # Calculate next due date (same as original PHP)
        from dateutil.relativedelta import relativedelta
        next_due_date = customer.date_delivered + relativedelta(months=payments_made + 1)
        
        # Calculate days overdue (same as original PHP)
        days_until_due = (next_due_date - date.today()).days
        days_overdue = max(0, -days_until_due) if days_until_due < 0 else 0
        
        # Calculate balance
        total_contract = (customer.monthly_due * customer.term) if customer.term else 0
        balance = total_contract - total_paid
        
        # Determine status (same logic as original PHP)
        if days_until_due < 0:
            status = 'overdue'
            status_class = 'status-overdue'
            status_text = 'Overdue'
            stats['overdue_customers'] += 1
            stats['total_overdue_amount'] += customer.monthly_due * overdue_payments
        elif 0 <= days_until_due <= 7:
            status = 'due_soon'
            status_class = 'status-due-soon'
            status_text = 'Due Soon'
            stats['due_soon_customers'] += 1
        else:
            status = 'current'
            status_class = 'status-current'
            status_text = 'Current'
            stats['current_customers'] += 1
        
        customer_data = {
            'customer': customer,
            'payments_made': payments_made,
            'expected_payments': expected_payments,
            'overdue_payments': overdue_payments,
            'next_due_date': next_due_date,
            'days_overdue': days_overdue,
            'days_until_due': days_until_due,
            'balance': balance,
            'status': status,
            'status_class': status_class,
            'status_text': status_text,
            'total_paid': total_paid
        }
        
        # Apply filters (same as original PHP)
        if filter_status == 'all' or \
           (filter_status == 'overdue' and status == 'overdue') or \
           (filter_status == 'due_soon' and status == 'due_soon') or \
           (filter_status == 'current' and status == 'current'):
            customers_data.append(customer_data)
        
        stats['total_customers'] += 1
    
    # Sort by overdue payments desc, then days overdue desc (same as original PHP)
    customers_data.sort(key=lambda x: (x['overdue_payments'], x['days_overdue']), reverse=True)
    
    context = {
        'customers_data': customers_data,
        'stats': stats,
        'filter_status': filter_status,
    }
    
    return render(request, 'reports/due_payments.html', context)

@login_required
def customer_history(request):
    """Customer history page - matches original arjensystem exactly"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Handle status change requests (mark as fully paid or pulled out) and restore items
    if request.method == 'POST' and 'action' in request.POST:
        action = request.POST.get('action')
        
        # Handle restore item action
        if action == 'restore_item':
            if request.user.role != 'admin':
                return JsonResponse({'success': False, 'message': 'Access denied. Only admins can restore items.'})
            
            history_id = request.POST.get('history_id')
            
            try:
                # Get the CustomerHistory record
                history_record = CustomerHistory.objects.get(id=history_id)
                
                # Check if this is an individual item pullout (has ITEM-PULLOUT in transaction number)
                if 'ITEM-PULLOUT' in history_record.transaction_number:
                    # This is an individual item - restore it to CustomerItem
                    try:
                        # Find the corresponding CustomerItem by matching details
                        customer_item = CustomerItem.objects.get(
                            customer__id=history_record.original_customer_id,
                            item_name=history_record.item_name,
                            status='pulled_out'
                        )
                        
                        # Restore the item to active status
                        customer_item.status = 'active'
                        customer_item.save()
                        
                        # Delete the history record
                        history_record.delete()
                        
                        # Log activity
                        UserActivityLog.objects.create(
                            user=request.user,
                            action='Item Restored',
                            model_name='CustomerItem',
                            object_id=customer_item.id,
                            description=f'Item "{customer_item.item_name}" restored from Customer History for customer {customer_item.customer.customers_name}',
                            ip_address=get_client_ip(request)
                        )
                        
                        return JsonResponse({'success': True, 'message': f'Item "{history_record.item_name}" restored successfully'})
                        
                    except CustomerItem.DoesNotExist:
                        return JsonResponse({'success': False, 'message': 'Original item record not found'})
                else:
                    # This is a full customer pullout - restore entire customer
                    try:
                        # Find or create the customer record
                        customer, created = Customer.objects.get_or_create(
                            id=history_record.original_customer_id,
                            defaults={
                                'customers_name': history_record.customers_name,
                                'address': history_record.address,
                                'contact': history_record.contact,
                                'date_delivered': history_record.date_delivered,
                                'item': history_record.item_name,
                                'term': history_record.term,
                                'monthly_due': history_record.total_amount / history_record.term if history_record.term > 0 else 0,
                                'status': 'active'
                            }
                        )
                        
                        if not created:
                            # Update existing customer to active
                            customer.status = 'active'
                            customer.completion_date = None
                            customer.save()
                        
                        # Delete the history record
                        history_record.delete()
                        
                        # Log activity
                        UserActivityLog.objects.create(
                            user=request.user,
                            action='Customer Restored',
                            model_name='Customer',
                            object_id=customer.id,
                            description=f'Customer "{customer.customers_name}" restored from Customer History',
                            ip_address=get_client_ip(request)
                        )
                        
                        return JsonResponse({'success': True, 'message': f'Customer "{history_record.customers_name}" restored successfully'})
                        
                    except Exception as e:
                        return JsonResponse({'success': False, 'message': f'Error restoring customer: {str(e)}'})
                        
            except CustomerHistory.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'History record not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
        
        # Handle other actions (existing functionality)
        customer_id = request.POST.get('customer_id')
        reason = request.POST.get('reason', '')
        notes = request.POST.get('notes', '')
        
        try:
            customer = Customer.objects.get(id=customer_id)
            
            # Calculate total amount paid
            total_paid = PaymentRecord.objects.filter(customer=customer).aggregate(
                total=Sum('amount_paid')
            )['total'] or 0
            
            status = 'fully_paid' if action == 'mark_fully_paid' else 'pulled_out'
            completion_date = date.today()
            
            # Create history record (using try/except since table might not exist yet)
            try:
                CustomerHistory.objects.create(
                    original_customer_id=customer.id,
                    customers_name=customer.customers_name,
                    address=customer.address,
                    contact=customer.contact,
                    date_delivered=customer.date_delivered,
                    completion_date=completion_date,
                    total_amount=customer.monthly_due * customer.term,
                    total_payments=total_paid,
                    final_status=status,
                    item_name=customer.item,
                    item_model=extract_item_model(customer.item),
                    transaction_number=f'{status.upper()}-{completion_date.strftime("%Y%m%d")}-{customer.id:04d}',
                    completed_by=request.user,
                    term=customer.term
                )
                
                # Update customer status
                customer.status = status
                customer.completion_date = completion_date
                customer.save()
                
                messages.success(request, f'Customer marked as {status.replace("_", " ")} successfully!')
            except Exception as e:
                messages.error(request, f'Error updating customer status: {str(e)}')
                
        except Customer.DoesNotExist:
            messages.error(request, 'Customer not found.')
    
    # Get history data (with fallback if table doesn't exist)
    try:
        fully_paid_customers = CustomerHistory.objects.filter(final_status='fully_paid').order_by('-completion_date')
        pulled_out_customers = CustomerHistory.objects.filter(final_status='pulled_out').order_by('-completion_date')
        
        # Get statistics
        stats = CustomerHistory.objects.aggregate(
            fully_paid_count=Count('id', filter=Q(final_status='fully_paid')),
            pulled_out_count=Count('id', filter=Q(final_status='pulled_out')),
            fully_paid_total=Sum('total_payments', filter=Q(final_status='fully_paid')),
            pulled_out_total=Sum('total_payments', filter=Q(final_status='pulled_out'))
        )
    except:
        # Fallback if CustomerHistory table doesn't exist yet
        fully_paid_customers = []
        pulled_out_customers = []
        stats = {
            'fully_paid_count': 0,
            'pulled_out_count': 0,
            'fully_paid_total': 0,
            'pulled_out_total': 0
        }
    
    context = {
        'fully_paid_customers': fully_paid_customers,
        'pulled_out_customers': pulled_out_customers,
        'stats': stats,
    }
    
    return render(request, 'reports/customer_history.html', context)

@login_required
def reports(request):
    """Reports dashboard - matches original arjensystem structure exactly"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Import additional required functions
    from django.db.models import Avg, DecimalField, Value
    from django.db.models.functions import Coalesce, TruncMonth
    from datetime import datetime, date
    
    # Get date range parameters (matches original)
    start_date = request.GET.get('start_date', date.today().replace(day=1).strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', date.today().strftime('%Y-%m-%d'))
    report_type = request.GET.get('report_type', 'overview')
    
    # Convert to datetime objects for queries
    try:
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
    except:
        start_datetime = date.today().replace(day=1)
        end_datetime = date.today()
    
    # Monthly collection report (matches original query structure)
    monthly_data = PaymentRecord.objects.filter(
        payment_date__range=[start_datetime, end_datetime]
    ).annotate(
        month=TruncMonth('payment_date')
    ).values('month').annotate(
        total_payments=Count('id'),
        total_amount=Sum('amount_paid'),
        average_payment=Avg('amount_paid')
    ).order_by('-month')
    
    # Payment method analysis (matches original)
    payment_methods = PaymentRecord.objects.filter(
        payment_date__range=[start_datetime, end_datetime]
    ).values('payment_method').annotate(
        count=Count('id'),
        total_amount=Sum('amount_paid'),
        avg_amount=Avg('amount_paid')
    ).order_by('-total_amount')
    
    # Customer performance report (matches original complex query)
    customer_performance = Customer.objects.filter(
        status='active'
    ).annotate(
        payments_made=Count('payment_records'),
        total_paid=Coalesce(Sum('payment_records__amount_paid'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
        total_contract=F('monthly_due') * F('term'),
        remaining_balance=F('monthly_due') * F('term') - Coalesce(Sum('payment_records__amount_paid'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
        completion_percentage=Case(
            When(term__gt=0, then=(Count('payment_records') * 100.0 / F('term'))),
            default=Value(0),
            output_field=DecimalField(max_digits=5, decimal_places=2)
        )
    ).order_by('-completion_percentage')[:20]
    
    # Overall statistics (matches original)
    total_customers = Customer.objects.filter(status='active').count()
    total_payments_period = PaymentRecord.objects.filter(
        payment_date__range=[start_datetime, end_datetime]
    ).count()
    total_amount_period = PaymentRecord.objects.filter(
        payment_date__range=[start_datetime, end_datetime]
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    active_customers_period = PaymentRecord.objects.filter(
        payment_date__range=[start_datetime, end_datetime]
    ).values('customer').distinct().count()
    avg_payment_period = PaymentRecord.objects.filter(
        payment_date__range=[start_datetime, end_datetime]
    ).aggregate(avg=Avg('amount_paid'))['avg'] or 0
    
    # Top performing customers (matches original)
    top_customers = Customer.objects.filter(
        status='active',
        payment_records__payment_date__range=[start_datetime, end_datetime]
    ).annotate(
        payments_made_count=Count('payment_records'),  # FIXED: Renamed to avoid conflict with @property
        total_paid_amount=Sum('payment_records__amount_paid')  # FIXED: Renamed to avoid conflict
    ).order_by('-total_paid_amount')[:10]
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'report_type': report_type,
        'monthly_data': monthly_data,
        'payment_methods': payment_methods,
        'customer_performance': customer_performance,
        'total_customers': total_customers,
        'total_payments_period': total_payments_period,
        'total_amount_period': total_amount_period,
        'active_customers_period': active_customers_period,
        'avg_payment_period': avg_payment_period,
        'top_customers': top_customers,
    }
    
    return render(request, 'reports/reports.html', context)

@login_required
def manage_users(request):
    """Manage users page - Admin only - matches original arjensystem exactly"""
    if request.user.role != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('index')
    
    # Handle user approval
    if request.method == 'POST' and 'approve_user' in request.POST:
        user_id = request.POST.get('user_id')
        try:
            user = CustomUser.objects.get(id=user_id)
            user.status = 'active'
            user.save()
            messages.success(request, f'User {user.username} approved successfully! Use the "Link Customer" button to manually link this user to a customer account if needed.')
        except CustomUser.DoesNotExist:
            messages.error(request, 'User not found.')
    
    # Handle user rejection
    if request.method == 'POST' and 'reject_user' in request.POST:
        user_id = request.POST.get('user_id')
        try:
            user = CustomUser.objects.get(id=user_id)
            user.status = 'inactive'  # Using inactive instead of rejected
            user.save()
            messages.success(request, 'User registration rejected.')
        except CustomUser.DoesNotExist:
            messages.error(request, 'User not found.')
    
    # Handle customer linking
    if request.method == 'POST' and 'link_customer' in request.POST:
        user_id = request.POST.get('link_user_id')
        customer_id = request.POST.get('customer_link_id')
        
        if user_id and customer_id:
            try:
                user = CustomUser.objects.get(id=user_id)
                customer = Customer.objects.get(id=customer_id)
                
                # Check if customer is already linked
                existing_link = CustomUser.objects.filter(customer_id=customer_id).exclude(id=user_id).first()
                if existing_link:
                    messages.error(request, f'Customer is already linked to user: {existing_link.full_name} ({existing_link.username})')
                else:
                    user.customer_id = customer_id
                    user.save()
                    messages.success(request, f'Customer account linked successfully! {user.full_name} is now linked to {customer.customers_name}')
            except (CustomUser.DoesNotExist, Customer.DoesNotExist):
                messages.error(request, 'Invalid user or customer selection.')
        else:
            messages.error(request, 'Invalid user or customer selection.')
    
    # Handle user deletion
    if request.method == 'GET' and 'delete' in request.GET:
        user_id = request.GET.get('delete')
        if user_id and int(user_id) != request.user.id:
            try:
                user = CustomUser.objects.get(id=user_id)
                user.delete()
                messages.success(request, 'User deleted successfully!')
            except CustomUser.DoesNotExist:
                messages.error(request, 'User not found.')
        else:
            messages.error(request, 'You cannot delete your own account!')
    
    # Get pending users (status = 'pending')
    pending_users = CustomUser.objects.filter(status='pending').order_by('-created_at')
    
    # Get only active users with customer information (matches original arjensystem)
    all_users = CustomUser.objects.filter(status='active').select_related().order_by('-created_at')
    
    # Get unlinked customers for dropdown
    unlinked_customers = Customer.objects.filter(
        status='active'
    ).exclude(
        id__in=CustomUser.objects.filter(customer_id__isnull=False).values_list('customer_id', flat=True)
    ).order_by('customers_name')
    
    context = {
        'pending_users': pending_users,
        'all_users': all_users,
        'unlinked_customers': unlinked_customers,
    }
    
    return render(request, 'admin/manage_users.html', context)

@login_required
def customer_detail(request, customer_id):
    """Customer detail view"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    messages.info(request, 'Customer detail page - Coming soon!')
    return redirect('customers_list')

@login_required
def edit_customer(request, customer_id):
    """Edit customer view - matches original arjensystem functionality"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    # Handle AJAX requests for item management
    if request.method == 'POST' and 'action' in request.POST:
        if request.POST['action'] == 'remove_item' and 'item_id' in request.POST:
            item_id = int(request.POST['item_id'])
            
            try:
                # Get the item to remove
                item = CustomerItem.objects.get(id=item_id)
                customer = item.customer
                
                # Calculate remaining balance for this specific item
                item_payments = PaymentRecord.objects.filter(customer_item=item).aggregate(
                    total=Sum('amount_paid'))['total'] or Decimal('0.00')
                item_contract_amount = item.total_contract_amount
                remaining_balance = item_contract_amount - item_payments
                
                # Get transaction number from request or generate one
                transaction_number = request.POST.get('transaction_number', f'ITEM-PULLOUT-{timezone.now().strftime("%Y%m%d")}-{item_id:04d}')
                
                # Create CustomerHistory record for this specific item
                CustomerHistory.objects.create(
                    original_customer_id=customer.id,
                    customers_name=customer.customers_name,
                    address=customer.address,
                    contact=customer.contact,
                    date_delivered=item.purchase_date or timezone.now().date(),
                    completion_date=timezone.now().date(),
                    total_amount=item_contract_amount,  # Contract amount for this item
                    total_payments=remaining_balance,  # Remaining balance for this item
                    final_status='pulled_out',
                    item_name=item.item_name,
                    item_model=extract_item_model(item.item_name),
                    transaction_number=transaction_number,
                    completed_by=request.user,
                    term=item.term_months
                )
                
                # Mark the item as pulled out (not deleted)
                item.status = 'pulled_out'
                item.save()
                
                # Log activity
                UserActivityLog.objects.create(
                    user=request.user,
                    action='Individual Item Pullout',
                    model_name='CustomerItem',
                    object_id=item.id,
                    description=f'Item "{item.item_name}" pulled out from customer {customer.customers_name}. Transaction: {transaction_number}',
                    ip_address=get_client_ip(request)
                )
                
                return JsonResponse({'success': True, 'message': f'Item "{item.item_name}" removed successfully and added to Customer History'})
            except CustomerItem.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Item not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
        
        elif request.POST['action'] == 'edit_item' and 'item_id' in request.POST:
            item_id = int(request.POST['item_id'])
            
            try:
                # Get the item to edit
                item = CustomerItem.objects.get(id=item_id)
                
                # Get form data
                item_name = request.POST.get('item_name', '').strip()
                item_model = request.POST.get('item_model', '').strip()
                original_price = Decimal(request.POST.get('original_price', '0'))
                downpayment = Decimal(request.POST.get('downpayment', '0'))
                monthly_due = Decimal(request.POST.get('monthly_due', '0'))
                term_months = int(request.POST.get('term_months', 0))
                
                # Calculate contract details
                from datetime import datetime
                from dateutil.relativedelta import relativedelta
                
                total_contract_amount = (monthly_due * term_months) + downpayment
                purchase_date = item.purchase_date or datetime.now().date()
                contract_start_date = purchase_date
                contract_end_date = purchase_date + relativedelta(months=term_months)
                first_due_date = purchase_date + relativedelta(months=1)
                
                # Update the item
                item.item_name = item_name
                item.item_model = item_model
                item.original_price = original_price
                item.item_price = original_price
                item.downpayment = downpayment
                item.monthly_due = monthly_due
                item.term_months = term_months
                item.total_contract_amount = total_contract_amount
                item.contract_start_date = contract_start_date
                item.contract_end_date = contract_end_date
                item.first_due_date = first_due_date
                item.save()
                
                return JsonResponse({'success': True, 'message': 'Item updated successfully'})
            except CustomerItem.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Item not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    try:
        customer = Customer.objects.get(id=customer_id)
        
        # Handle form submission for updating customer
        if request.method == 'POST' and 'update' in request.POST:
            customers_name = request.POST.get('customers_name')
            address = request.POST.get('address')
            contact = request.POST.get('contact')
            date_delivered = request.POST.get('date_delivered')
            term = int(request.POST.get('term', 0))
            rebates = Decimal(request.POST.get('rebates', '0'))
            monthly_due = Decimal(request.POST.get('monthly_due', '0'))
            
            # New fields
            item_name = request.POST.get('item_name')
            item_model = request.POST.get('item_model')
            original_price = Decimal(request.POST.get('original_price', '0'))
            downpayment = Decimal(request.POST.get('downpayment', '0'))
            
            # Create combined item field for legacy compatibility
            item = f"{item_name} {item_model}"
            
            try:
                # Calculate total contract amount
                total_contract_amount = (monthly_due * term) + downpayment
                
                # Update customers table
                customer.customers_name = customers_name
                customer.address = address
                customer.contact = contact
                customer.date_delivered = date_delivered
                customer.item = item
                customer.term = term
                customer.rebates = rebates
                customer.monthly = monthly_due
                customer.monthly_due = monthly_due
                customer.amount = total_contract_amount
                customer.downpayment = downpayment
                customer.save()
                
                # Check if customer has items in customer_items table
                customer_items = CustomerItem.objects.filter(customer=customer, status='active')
                
                # Calculate contract details
                from datetime import datetime
                from dateutil.relativedelta import relativedelta
                
                date_delivered_obj = datetime.strptime(date_delivered, '%Y-%m-%d').date()
                contract_start_date = date_delivered_obj
                contract_end_date = date_delivered_obj + relativedelta(months=term)
                first_due_date = date_delivered_obj + relativedelta(months=1)
                
                if customer_items.exists():
                    # Update existing customer_items record
                    item_record = customer_items.first()
                    item_record.item_name = item_name
                    item_record.item_model = item_model
                    item_record.item_description = ''  # Add default empty description
                    item_record.item_price = original_price  # Set item_price to original_price
                    item_record.quantity = 1  # Set default quantity
                    item_record.original_price = original_price
                    item_record.downpayment = downpayment
                    item_record.good_as_cash = 'no'  # Add missing required field
                    item_record.rebate_amount = rebates  # Add missing required field
                    item_record.monthly_due = monthly_due
                    item_record.term_months = term
                    item_record.total_contract_amount = total_contract_amount
                    item_record.purchase_date = date_delivered_obj
                    item_record.contract_start_date = contract_start_date
                    item_record.contract_end_date = contract_end_date
                    item_record.first_due_date = first_due_date
                    item_record.save()
                else:
                    # Create new customer_items record for legacy customers
                    CustomerItem.objects.create(
                        customer=customer,
                        item_name=item_name,
                        item_model=item_model,
                        item_description='',  # Add default empty description
                        item_price=original_price,  # Set item_price to original_price
                        quantity=1,  # Set default quantity
                        original_price=original_price,
                        downpayment=downpayment,
                        good_as_cash='no',  # Add missing required field
                        rebate_amount=rebates,  # Add missing required field
                        monthly_due=monthly_due,
                        term_months=term,
                        total_contract_amount=total_contract_amount,
                        purchase_date=date_delivered_obj,
                        contract_start_date=contract_start_date,
                        contract_end_date=contract_end_date,
                        first_due_date=first_due_date,
                        status='active'
                    )
                
                messages.success(request, 'Customer updated successfully!')
                return redirect('customers_list')
                
            except Exception as e:
                messages.error(request, f'Error updating customer: {str(e)}')
        
        # Get customer items
        customer_items = CustomerItem.objects.filter(customer=customer, status='active').order_by('-purchase_date')
        
        context = {
            'customer': customer,
            'customer_items': customer_items,
            'page_title': f'Edit {customer.customers_name}'
        }
        return render(request, 'customers/edit_customer.html', context)
        
    except Customer.DoesNotExist:
        messages.error(request, 'Customer not found')
        return redirect('customers_list')

@login_required
def remove_customer(request, customer_id):
    """Remove customer functionality - matches original arjensystem"""
    if request.user.role != 'admin':
        messages.error(request, 'Access denied. Only admins can remove customers.')
        return redirect('customers_list')
    
    if request.method == 'POST':
        try:
            customer = Customer.objects.get(id=customer_id)
            removal_type = request.POST.get('removal_type')
            removal_reason = request.POST.get('removal_reason', '')
            transaction_number = request.POST.get('transaction_number', '')
            
            if removal_type == 'pullout':
                # Archive customer - set status to inactive
                customer.status = 'inactive'
                customer.save()
                
                # Calculate remaining balance (what customer still owes)
                total_paid = PaymentRecord.objects.filter(customer=customer).aggregate(
                    total=Sum('amount_paid'))['total'] or Decimal('0.00')
                remaining_balance = (customer.monthly_due * customer.term) - total_paid
                
                # Use provided transaction number or generate one as fallback
                if not transaction_number.strip():
                    transaction_number = f'PULLOUT-{timezone.now().strftime("%Y%m%d")}-{customer.id:04d}'
                
                # Log the pullout in customer history
                CustomerHistory.objects.create(
                    original_customer_id=customer.id,
                    customers_name=customer.customers_name,  # Customer Name
                    address=customer.address,
                    contact=customer.contact,
                    date_delivered=customer.date_delivered or timezone.now().date(),
                    completion_date=timezone.now().date(),
                    total_amount=customer.amount,  # Contract Amount (Gross Price from customer list)
                    total_payments=remaining_balance,  # Amount Paid (Remaining balance from payment history)
                    final_status='pulled_out',  # Status
                    item_name=customer.item,  # Item Name from customer list
                    item_model=extract_item_model(customer.item),  # Extract actual model from item name
                    transaction_number=transaction_number,  # Transaction # from form
                    completed_by=request.user,  # Completed By (who transacted this)
                    term=customer.term  # Term from customer list
                )
                
                # Log activity
                UserActivityLog.objects.create(
                    user=request.user,
                    action='Customer Pullout',
                    model_name='Customer',
                    object_id=customer.id,
                    description=f'Customer {customer.customers_name} pulled out (archived). Reason: {removal_reason}',
                    ip_address=get_client_ip(request)
                )
                
                messages.success(request, f'Customer {customer.customers_name} has been successfully archived.')
                
            elif removal_type == 'permanent':
                # Permanent deletion - remove payment records first, then customer
                customer_name = customer.customers_name
                
                # Delete payment records
                PaymentRecord.objects.filter(customer=customer).delete()
                
                # Delete customer items
                CustomerItem.objects.filter(customer=customer).delete()
                
                # Delete customer history
                CustomerHistory.objects.filter(original_customer_id=customer.id).delete()
                
                # Log activity before deletion
                UserActivityLog.objects.create(
                    user=request.user,
                    action='Customer Deletion',
                    model_name='Customer',
                    object_id=customer.id,
                    description=f'Customer {customer_name} permanently deleted. Reason: {removal_reason}',
                    ip_address=get_client_ip(request)
                )
                
                # Delete customer
                customer.delete()
                
                messages.success(request, f'Customer {customer_name} has been permanently deleted.')
            
        except Customer.DoesNotExist:
            messages.error(request, 'Customer not found.')
        except Exception as e:
            messages.error(request, f'Error removing customer: {str(e)}')
    
    return redirect('customers_list')

def migrate_customers_to_items():
    """Utility function to create CustomerItem records for existing customers"""
    from datetime import date
    from dateutil.relativedelta import relativedelta
    
    customers_without_items = Customer.objects.filter(items__isnull=True).distinct()
    migrated_count = 0
    
    for customer in customers_without_items:
        try:
            # Calculate contract dates
            purchase_date = customer.date_delivered
            contract_start_date = purchase_date
            contract_end_date = purchase_date + relativedelta(months=customer.term)
            first_due_date = purchase_date + relativedelta(months=1)
            
            # Create CustomerItem record
            CustomerItem.objects.create(
                customer=customer,
                item_name=customer.item,
                item_model='',
                item_description='',
                item_price=customer.amount,
                quantity=1,
                original_price=customer.amount,
                downpayment=customer.downpayment,
                good_as_cash='no',
                rebate_amount=customer.rebates,
                monthly_due=customer.monthly_due,
                term_months=customer.term,
                total_contract_amount=customer.amount,
                purchase_date=purchase_date,
                contract_start_date=contract_start_date,
                contract_end_date=contract_end_date,
                first_due_date=first_due_date,
                status='active'
            )
            
            migrated_count += 1
            print(f"DEBUG: Migrated {customer.customers_name}: term={customer.term}, monthly_due={customer.monthly_due}")
            
        except Exception as e:
            print(f"DEBUG: Failed to migrate {customer.customers_name}: {e}")
    
    print(f"DEBUG: Migration complete: {migrated_count} customers migrated to CustomerItem system")
    return migrated_count

@login_required
def customer_payments(request, customer_id):
    """Customer payments view - matches original arjensystem functionality"""
    if request.user.role not in ['admin', 'staff']:
        messages.error(request, 'Access denied')
        return redirect('index')
    
    try:
        customer = Customer.objects.get(id=customer_id)
        
        # Get active items for this customer with optimized payment calculations
        active_items = customer.items.filter(status='active').prefetch_related('payments').order_by('-purchase_date')
        
        # Calculate payment data for each item (optimized with prefetch)
        for item in active_items:
            # Use prefetched payments to avoid additional queries
            item_payments = item.payments.all()
            
            # Calculate total deductions toward this item's contract (payment + rebate)
            total_deductions = Decimal('0.00')
            for payment in item_payments:
                total_deductions += payment.amount_paid + (payment.rebate_amount or Decimal('0.00'))
            
            # Item-specific payment data
            item.total_paid = total_deductions
            item.remaining_balance = item.total_contract_amount - item.total_paid
            
            # Determine how many full monthly dues have been covered for this item
            if item.monthly_due and item.term_months:
                full_months_paid = int(total_deductions // item.monthly_due)
                if full_months_paid > item.term_months:
                    full_months_paid = item.term_months
            else:
                full_months_paid = 0
            
            item.payments_made_count = full_months_paid
            item.payments_remaining_count = max(0, item.term_months - item.payments_made_count)
            
            # Calculate payment progress percentage based on fully covered months
            if item.term_months > 0:
                item.payment_progress_percentage = (item.payments_made_count / item.term_months * 100)
            else:
                item.payment_progress_percentage = 0
        
        customer.active_items = active_items
        
        # Get all payments for this customer (for overall summary and breakdown)
        payments = PaymentRecord.objects.filter(customer=customer).select_related('customer_item').order_by('payment_date')
        
        # Calculate payment summary using REAL ITEM DATA (not old customer data)
        total_paid = sum(payment.amount_paid for payment in payments)
        total_paid_with_rebates = sum(payment.amount_paid + (payment.rebate_amount or 0) for payment in payments)
        
        # SMART FALLBACK: Use CustomerItem data if available, otherwise use clean Customer data
        if active_items.exists():
            # Use the first active item's data (or sum all items if multiple)
            first_item = active_items.first()
            total_contract = first_item.monthly_due * first_item.term_months
            actual_term = first_item.term_months
        else:
            # FALLBACK: Use Customer data but ensure it's not corrupted by payment recording
            # Use the ORIGINAL customer data, not the corrupted payment totals
            total_contract = customer.monthly_due * customer.term
            actual_term = customer.term
            
        # Calculate balance using running balance from payment records (like admin does)
        # The admin shows PHP 6,549 as the final balance in the payment table
        # This is the running balance after all payments and rebates
        
        # Get the final running balance from the last payment record
        last_payment = payments.order_by('payment_date', 'id').last()
        if last_payment and hasattr(last_payment, 'running_balance'):
            # Use the running balance from the last payment record
            balance = last_payment.running_balance
        else:
            # Fallback to calculation: Contract - (Payments + Rebates)
            balance = total_contract - total_paid_with_rebates
        
        # Ensure all customer items use correct calculated contract amounts
        # Fix any contract amount discrepancies in the database
        for active_item in active_items:
            calculated_contract = active_item.monthly_due * active_item.term_months if active_item.monthly_due and active_item.term_months else Decimal('0.00')
            if abs(active_item.total_contract_amount - calculated_contract) > Decimal('0.01'):
                active_item.total_contract_amount = calculated_contract
                active_item.save()
        
        # Recalculate total contract with corrected values
        if active_items.exists():
            first_item = active_items.first()
            total_contract = first_item.monthly_due * first_item.term_months
        
        # Recalculate balance with corrected contract
        balance = total_contract - total_paid_with_rebates

        # Calculate 'payments made' based on fully covered monthly dues
        payments_made = 0
        term_for_summary = actual_term

        # Determine the monthly due used for the overall summary
        if active_items.exists():
            summary_monthly_due = active_items.first().monthly_due
        else:
            summary_monthly_due = customer.monthly_due

        if summary_monthly_due and term_for_summary:
            # Ensure we work with Decimals for safe division
            if isinstance(total_paid_with_rebates, Decimal):
                total_deductions_for_months = total_paid_with_rebates
            else:
                total_deductions_for_months = Decimal(str(total_paid_with_rebates))
            
            full_months_paid = int(total_deductions_for_months // summary_monthly_due)
            if full_months_paid > term_for_summary:
                full_months_paid = term_for_summary
            payments_made = full_months_paid

        payments_remaining = max(0, term_for_summary - payments_made)
        
        # Calculate progress percentage using actual term
        progress_percentage = (payments_made / term_for_summary * 100) if term_for_summary > 0 else 0
        
        # Create empty payment breakdown - will be populated by JavaScript when item is selected
        payment_breakdown = []
        
        # Prepare payments data for JavaScript (universal for all customers)
        import json
        payments_json = []
        for payment in payments:
            payments_json.append({
                'id': payment.id,
                'customer_item_id': payment.customer_item.id if payment.customer_item else None,
                'payment_date': payment.payment_date.strftime('%b %d, %Y'),
                'amount_paid': float(payment.amount_paid),
                'rebate_amount': float(payment.rebate_amount or 0),
                'payment_method': payment.payment_method,
                'transaction_number': payment.transaction_number or '',
                'recorded_by': payment.recorded_by.username if payment.recorded_by else 'System',
                'notes': payment.notes or '',
                # New fields for showing time in payment breakdown
                'created_at': payment.created_at.strftime('%b %d, %Y, %I:%M:%S %p') if payment.created_at else '',
                'created_time': payment.created_at.strftime('%I:%M:%S %p') if payment.created_at else ''
            })
        
        context = {
            'customer': customer,
            'payments': payments,
            'payments_json': json.dumps(payments_json),  # Add JSON data for JavaScript
            'total_paid': total_paid_with_rebates,  # FIXED: Use rebate-inclusive total
            'total_contract': total_contract,
            'balance': balance,
            'payments_made': payments_made,
            'payments_remaining': payments_remaining,
            'actual_term': actual_term,  # Pass the correct term to template
            'progress_percentage': min(100, progress_percentage),
            'payment_breakdown': payment_breakdown,
            'page_title': f'Payments - {customer.customers_name}'
        }
        return render(request, 'customers/customer_payments.html', context)
        
    except Customer.DoesNotExist:
        messages.error(request, 'Customer not found')
        return redirect('customers_list')





def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# Profile Update Functions
@login_required
def edit_profile(request):
    """Edit profile page for all roles"""
    user = request.user
    if request.method == 'POST':
        form = CustomUserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            # Prefer to go back to the page where the modal was opened
            referer = request.META.get('HTTP_REFERER')
            if referer:
                return redirect(referer)
            # Fallback by role
            if user.role == 'admin':
                return redirect('admin_dashboard')
            elif user.role == 'staff':
                return redirect('staff_dashboard')
            else:
                return redirect('customer_dashboard')
    else:
        form = CustomUserEditForm(instance=user)
    return render(request, 'account/edit_profile.html', {
        'form': form
    })

@login_required
def get_profile_data(request):
    """Return current user's profile data with sensible fallbacks (JSON)."""
    user = request.user
    phone = getattr(user, 'phone', '') or ''
    # Fallback for customers: use Customer.contact if user.phone is blank
    if (not phone) and getattr(user, 'role', '') == 'customer' and getattr(user, 'customer_id', None):
        try:
            customer = Customer.objects.get(id=user.customer_id)
            phone = customer.contact or ''
        except Customer.DoesNotExist:
            phone = ''
    data = {
        'username': getattr(user, 'username', ''),
        'full_name': getattr(user, 'full_name', ''),
        'email': getattr(user, 'email', ''),
        'phone': phone,
    }
    return JsonResponse({'success': True, 'profile': data})

@login_required
def customer_update_profile(request):
    """Update customer profile"""
    if request.method == 'POST':
        try:
            user = request.user
            user.full_name = request.POST.get('full_name', '').strip()
            user.email = request.POST.get('email', '').strip()
            
            # Update password if provided
            new_password = request.POST.get('new_password', '').strip()
            if new_password:
                user.set_password(new_password)
            
            user.save()
            
            messages.success(request, 'Profile updated successfully!')
            return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})
            
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
            return JsonResponse({'success': False, 'message': f'Error updating profile: {str(e)}'})
    
    return redirect('customer_dashboard')


@login_required
def staff_update_profile(request):
    """Update staff profile"""
    if request.method == 'POST':
        try:
            user = request.user
            user.full_name = request.POST.get('full_name', '').strip()
            user.username = request.POST.get('username', '').strip()
            user.email = request.POST.get('email', '').strip()
            
            # Update password if provided
            new_password = request.POST.get('new_password', '').strip()
            if new_password:
                user.set_password(new_password)
            
            user.save()
            
            messages.success(request, 'Profile updated successfully!')
            return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})
            
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
            return JsonResponse({'success': False, 'message': f'Error updating profile: {str(e)}'})
    
    return redirect('staff_dashboard')


@login_required
def admin_update_profile(request):
    """Update admin profile"""
    if request.method == 'POST':
        try:
            user = request.user
            user.full_name = request.POST.get('full_name', '').strip()
            user.username = request.POST.get('username', '').strip()
            user.email = request.POST.get('email', '').strip()
            
            # Update password if provided
            new_password = request.POST.get('new_password', '').strip()
            if new_password:
                user.set_password(new_password)
            
            user.save()
            
            messages.success(request, 'Profile updated successfully!')
            return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})
            
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
            return JsonResponse({'success': False, 'message': f'Error updating profile: {str(e)}'})
    
    return redirect('admin_dashboard')

@login_required
def get_customer_items(request, customer_id):
    """API endpoint to get customer items for payment form"""
    try:
        customer = Customer.objects.get(id=customer_id)
        # Only return active items (not completed or pulled out) for this customer
        items = CustomerItem.objects.filter(customer=customer, status='active')
        
        items_data = []
        for item in items:
            items_data.append({
                'id': item.id,
                'item_name': item.item_name,
                'item_model': item.item_model,
                'monthly_due': float(item.monthly_due),
                'total_contract_amount': float(item.total_contract_amount)
            })
        
        return JsonResponse({
            'success': True,
            'items': items_data
        })
        
    except Customer.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Customer not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
