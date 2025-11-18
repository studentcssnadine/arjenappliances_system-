# Data migration to populate transaction numbers for existing payment records

from django.db import migrations
from datetime import datetime


def populate_transaction_numbers(apps, schema_editor):
    PaymentRecord = apps.get_model('myapp', 'PaymentRecord')
    
    # Get all payment records without transaction numbers
    payments_without_txn = PaymentRecord.objects.filter(transaction_number__isnull=True) | PaymentRecord.objects.filter(transaction_number='')
    
    for payment in payments_without_txn:
        # Generate transaction number based on payment date
        if payment.payment_date:
            year_month = payment.payment_date.strftime('%Y-%m')
        else:
            year_month = datetime.now().strftime('%Y-%m')
        
        # Find the next available number for this month
        existing_txns = PaymentRecord.objects.filter(
            transaction_number__startswith=f'TXN-{year_month}-'
        ).exclude(id=payment.id)
        
        if existing_txns.exists():
            # Get the highest number
            max_num = 0
            for txn in existing_txns:
                try:
                    num = int(txn.transaction_number.split('-')[-1])
                    max_num = max(max_num, num)
                except (ValueError, IndexError):
                    continue
            new_number = max_num + 1
        else:
            new_number = 1
        
        # Assign the transaction number
        payment.transaction_number = f"TXN-{year_month}-{new_number:04d}"
        payment.save()


def reverse_populate_transaction_numbers(apps, schema_editor):
    # This is irreversible, but we can clear the transaction numbers if needed
    PaymentRecord = apps.get_model('myapp', 'PaymentRecord')
    PaymentRecord.objects.all().update(transaction_number='')


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0008_enhance_payment_system'),
    ]

    operations = [
        migrations.RunPython(
            populate_transaction_numbers,
            reverse_populate_transaction_numbers,
        ),
    ]
