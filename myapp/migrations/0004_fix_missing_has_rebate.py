from django.db import migrations

SQL_ADD_HAS_REBATE = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='myapp_paymentrecord' AND column_name='has_rebate'
    ) THEN
        ALTER TABLE myapp_paymentrecord ADD COLUMN has_rebate boolean NOT NULL DEFAULT FALSE;
    END IF;
END$$;
"""

SQL_ADD_REBATE_AMOUNT = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='myapp_paymentrecord' AND column_name='rebate_amount'
    ) THEN
        ALTER TABLE myapp_paymentrecord ADD COLUMN rebate_amount numeric(10,2) NOT NULL DEFAULT 0;
    END IF;
END$$;
"""

class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0003_fix_missing_recorded_by"),
    ]

    operations = [
        migrations.RunSQL(SQL_ADD_HAS_REBATE),
        migrations.RunSQL(SQL_ADD_REBATE_AMOUNT),
    ]
