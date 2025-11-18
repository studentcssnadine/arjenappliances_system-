from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

class CustomUser(AbstractUser):
    """Extended User model for ArjenSystem with role-based access"""
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('customer', 'Customer'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
    ]
    
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    customer_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.full_name} ({self.role})"

class Customer(models.Model):
    """Main customer records for Arjen Appliances"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('fully_paid', 'Fully Paid'),
        ('pulled_out', 'Pulled Out'),
    ]
    
    customers_name = models.CharField(max_length=255)
    address = models.TextField()
    contact = models.CharField(max_length=50)
    date_delivered = models.DateField()
    item = models.CharField(max_length=255)
    monthly = models.DecimalField(max_digits=10, decimal_places=2)
    monthly_due = models.DecimalField(max_digits=10, decimal_places=2)
    term = models.IntegerField()  # Number of months
    rebates = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Total contract amount
    payments = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Total payments made
    downpayment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    completion_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.customers_name
    
    @property
    def balance(self):
        """Calculate remaining balance"""
        return self.amount - self.payments
    
    @property
    def payment_count(self):
        """Count of payments made"""
        return self.payment_records.count()
    
    @property
    def next_due_date(self):
        """Calculate next payment due date"""
        if self.payment_count >= self.term:
            return None
        return self.date_delivered + relativedelta(months=self.payment_count + 1)
    
    @property
    def is_overdue(self):
        """Check if customer has overdue payments"""
        next_due = self.next_due_date
        if next_due and next_due < date.today():
            return True
        return False
    
    @property
    def overdue_amount(self):
        """Calculate overdue amount"""
        if not self.is_overdue:
            return Decimal('0.00')
        
        months_overdue = 0
        current_date = date.today()
        check_date = self.date_delivered + relativedelta(months=self.payment_count + 1)
        
        while check_date < current_date and self.payment_count + months_overdue < self.term:
            months_overdue += 1
            check_date = self.date_delivered + relativedelta(months=self.payment_count + months_overdue + 1)
        
        return self.monthly * months_overdue
    
    @property
    def item_name(self):
        """Extract item name (everything before last space) - matches original arjensystem logic"""
        if not self.item:
            return "No items"
        
        item_text = self.item.strip()
        if not item_text:
            return "No items"
            
        # Find last space position (matches PHP strrpos logic)
        last_space_pos = item_text.rfind(' ')
        if last_space_pos != -1:
            return item_text[:last_space_pos].strip()
        else:
            return item_text
    
    @property
    def item_model(self):
        """Extract item model (everything after last space) - matches original arjensystem logic"""
        if not self.item:
            return ""
        
        item_text = self.item.strip()
        if not item_text:
            return ""
            
        # Find last space position (matches PHP strrpos logic)
        last_space_pos = item_text.rfind(' ')
        if last_space_pos != -1:
            return item_text[last_space_pos + 1:].strip()
        else:
            return ""
    
    @property
    def contract_value(self):
        """Calculate contract value (monthly_due * term) - matches original arjensystem"""
        return self.monthly_due * self.term
    
    @property
    def total_contract_display(self):
        """Format total amount display - matches original arjensystem gross_price_display logic"""
        total_contract = self.contract_value + self.downpayment
        
        if total_contract > 0:
            if self.term == 1:
                return "Same as cash"
            else:
                return f"PHP {total_contract:,.2f}"
        else:
            return "-"

class PaymentRecord(models.Model):
    """Individual payment tracking with transaction system"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payment_records')
    customer_item = models.ForeignKey('CustomerItem', on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    payment_number = models.IntegerField(null=True, blank=True)
    payment_date = models.DateField(default=date.today)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Cash')
    transaction_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    recorded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    has_rebate = models.BooleanField(default=False)
    rebate_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reference_id = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"Payment #{self.payment_number} - {self.customer.customers_name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate payment number if not set
        if not self.payment_number:
            last_payment = PaymentRecord.objects.filter(customer=self.customer).order_by('-payment_number').first()
            self.payment_number = (last_payment.payment_number + 1) if last_payment else 1
        
        # Auto-generate transaction number if not set or empty
        if not self.transaction_number or self.transaction_number.strip() == '':
            self.transaction_number = self.generate_transaction_number()
        
        super().save(*args, **kwargs)
        
        # Update customer's total payments
        self.customer.payments = self.customer.payment_records.aggregate(
            total=models.Sum('amount_paid')
        )['total'] or Decimal('0.00')
        self.customer.save()
    
    def generate_transaction_number(self):
        """Generate transaction number in format TXN-YYYY-MM-DDDD"""
        from datetime import datetime
        
        year_month = self.payment_date.strftime('%Y-%m') if self.payment_date else datetime.now().strftime('%Y-%m')
        
        # Find the next available number to avoid conflicts
        counter = 1
        while True:
            txn_number = f"TXN-{year_month}-{counter:04d}"
            # Exclude current record from check to avoid self-conflict
            if not PaymentRecord.objects.filter(transaction_number=txn_number).exclude(id=self.id).exists():
                return txn_number
            counter += 1
            
            # Safety check to prevent infinite loop
            if counter > 9999:
                # Fallback to timestamp-based number
                timestamp = datetime.now().strftime('%H%M%S')
                return f"TXN-{year_month}-{timestamp}"


class Transaction(models.Model):
    """Transaction number system"""
    transaction_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=50)  # payment, adjustment, etc.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Transaction {self.transaction_number}"

class MonthlyStatement(models.Model):
    """Billing system"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='monthly_statements')
    statement_date = models.DateField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('partial', 'Partial Payment'),
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-statement_date']
    
    def __str__(self):
        return f"Statement {self.statement_date} - {self.customer.customers_name}"

class CustomerHistory(models.Model):
    """Completed/archived customers - matches original arjensystem"""
    STATUS_CHOICES = [
        ('fully_paid', 'Fully Paid'),
        ('pulled_out', 'Pulled Out'),
    ]
    
    original_customer_id = models.IntegerField()  # Original customer ID
    customers_name = models.CharField(max_length=255)  # Matches actual DB
    address = models.TextField()
    contact = models.CharField(max_length=50)
    date_delivered = models.DateField()
    completion_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)  # Contract Amount (Gross Price)
    total_payments = models.DecimalField(max_digits=10, decimal_places=2)  # Amount Paid (Remaining Balance)
    final_status = models.CharField(max_length=15)  # Status
    archived_at = models.DateTimeField(auto_now_add=True)
    # Additional fields from migration 0008
    item_name = models.CharField(max_length=255, default='')  # Item Name
    item_model = models.CharField(max_length=255, default='')  # Item Model
    transaction_number = models.CharField(max_length=50, blank=True)  # Transaction #
    completed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)  # Completed By
    term = models.IntegerField(default=0)  # Term from customer list

    def __str__(self):
        return f"{self.customers_name} - {self.final_status}"

class UserPermission(models.Model):
    """Role-based permissions"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='permissions')
    permission_name = models.CharField(max_length=100)
    can_create = models.BooleanField(default=False)
    can_read = models.BooleanField(default=True)
    can_update = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.permission_name}"

class CustomerItem(models.Model):
    """Customer Items - tracks multiple items per customer"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=100)
    item_model = models.CharField(max_length=100)
    item_description = models.TextField(blank=True, default='')
    item_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity = models.IntegerField(default=1)
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    downpayment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    good_as_cash = models.CharField(max_length=3, choices=[('yes', 'Yes'), ('no', 'No')], default='no')
    rebate_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monthly_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    term_months = models.IntegerField(default=0)
    total_contract_amount = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_date = models.DateField()
    contract_start_date = models.DateField()
    contract_end_date = models.DateField()
    first_due_date = models.DateField()
    status = models.CharField(max_length=20, default='active', choices=[
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('pulled_out', 'Pulled Out')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.customers_name} - {self.item_name} {self.item_model}"

class UserActivityLog(models.Model):
    """Audit trail"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=50, blank=True)
    object_id = models.IntegerField(null=True, blank=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"
