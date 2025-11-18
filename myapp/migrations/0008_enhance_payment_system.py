# Generated manually for enhanced payment system

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0007_auto_20251027_0025'),
    ]

    operations = [
        # Add new fields to PaymentRecord
        migrations.AddField(
            model_name='paymentrecord',
            name='customer_item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='myapp.customeritem'),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='recorded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='has_rebate',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='rebate_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        
        # Modify transaction_number to be unique and not blank
        migrations.AlterField(
            model_name='paymentrecord',
            name='transaction_number',
            field=models.CharField(max_length=50, unique=True),
        ),
        
        # Add new fields to CustomerHistory
        migrations.AddField(
            model_name='customerhistory',
            name='item_name',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AddField(
            model_name='customerhistory',
            name='item_model',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AddField(
            model_name='customerhistory',
            name='transaction_number',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='customerhistory',
            name='completed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        
        # Note: CustomerHistory already has separate item_name and item_model fields
    ]
