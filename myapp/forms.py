from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Customer, PaymentRecord

class CustomerRegistrationForm(UserCreationForm):
    """Form for customer self-registration"""
    full_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your phone number'
        })
    )
    
    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'email', 'phone', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })

class CustomUserCreationForm(UserCreationForm):
    """Form for admin to create users"""
    full_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES)
    customer_id = forms.IntegerField(required=False)
    
    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'email', 'phone', 'role', 'customer_id', 'password1', 'password2')

class CustomUserEditForm(forms.ModelForm):
    """Form for users to edit their own profile"""
    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'email', 'phone')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
        }

class CustomerForm(forms.ModelForm):
    """Form for adding/editing customers"""
    
    class Meta:
        model = Customer
        fields = [
            'customers_name', 'address', 'contact', 'date_delivered', 'item',
            'monthly', 'monthly_due', 'term', 'rebates', 'amount', 'downpayment'
        ]
        widgets = {
            'customers_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter customer name'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter customer address'
            }),
            'contact': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter contact number'
            }),
            'date_delivered': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'item': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter item description'
            }),
            'monthly': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Monthly payment amount'
            }),
            'monthly_due': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Monthly due amount'
            }),
            'term': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of months'
            }),
            'rebates': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Rebate amount'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Total contract amount'
            }),
            'downpayment': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Down payment amount'
            }),
        }
    
    def clean_monthly(self):
        monthly = self.cleaned_data.get('monthly')
        if monthly and monthly <= 0:
            raise forms.ValidationError("Monthly payment must be greater than 0")
        return monthly
    
    def clean_term(self):
        term = self.cleaned_data.get('term')
        if term and (term <= 0 or term > 120):
            raise forms.ValidationError("Term must be between 1 and 120 months")
        return term
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError("Contract amount must be greater than 0")
        return amount

class PaymentForm(forms.ModelForm):
    """Form for recording payments"""
    
    class Meta:
        model = PaymentRecord
        fields = [
            'customer', 'payment_date', 'amount_paid', 'payment_method',
            'transaction_number', 'notes'
        ]
        widgets = {
            'customer': forms.Select(attrs={
                'class': 'form-control'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'amount_paid': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Payment amount'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-control'
            }, choices=[
                ('Cash', 'Cash'),
                ('Check', 'Check'),
                ('Bank Transfer', 'Bank Transfer'),
                ('GCash', 'GCash'),
                ('PayMaya', 'PayMaya'),
                ('Credit Card', 'Credit Card'),
            ]),
            'transaction_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Transaction/Reference number (optional)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe this payment (required notes)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(status='active').order_by('customers_name')
        self.fields['customer'].empty_label = "Select Customer"
        # Make notes required at the form level
        if 'notes' in self.fields:
            self.fields['notes'].required = True
