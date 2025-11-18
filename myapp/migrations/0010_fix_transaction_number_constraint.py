# Fix transaction number constraint issues

from django.db import migrations, models


def ensure_unique_transaction_numbers(apps, schema_editor):
    PaymentRecord = apps.get_model('myapp', 'PaymentRecord')
    
    # Handle any remaining empty or duplicate transaction numbers
    payments_without_txn = PaymentRecord.objects.filter(
        models.Q(transaction_number__isnull=True) | 
        models.Q(transaction_number='')
    )
    
    counter = 1
    for payment in payments_without_txn:
        # Generate a unique transaction number
        year_month = payment.payment_date.strftime('%Y-%m') if payment.payment_date else '2024-01'
        
        while True:
            txn_number = f"TXN-{year_month}-{counter:04d}"
            if not PaymentRecord.objects.filter(transaction_number=txn_number).exists():
                payment.transaction_number = txn_number
                payment.save()
                break
            counter += 1


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0009_populate_transaction_numbers'),
    ]

    operations = [
        migrations.RunPython(
            ensure_unique_transaction_numbers,
            migrations.RunPython.noop,
        ),
    ]
