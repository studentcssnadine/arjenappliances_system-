from django.db import migrations

SQL_ADD_COLUMN = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns 
        WHERE table_name='myapp_paymentrecord' AND column_name='recorded_by_id'
    ) THEN
        ALTER TABLE myapp_paymentrecord ADD COLUMN recorded_by_id BIGINT NULL;
    END IF;
END$$;
"""

SQL_ADD_CONSTRAINT = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'myapp_paymentrecord_recorded_by_id_fk'
    ) THEN
        ALTER TABLE myapp_paymentrecord
        ADD CONSTRAINT myapp_paymentrecord_recorded_by_id_fk
        FOREIGN KEY (recorded_by_id)
        REFERENCES myapp_customuser (id)
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END$$;
"""

SQL_ADD_INDEX = """
CREATE INDEX IF NOT EXISTS myapp_paymentrecord_recorded_by_id_idx
ON myapp_paymentrecord (recorded_by_id);
"""

class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(SQL_ADD_COLUMN),
        migrations.RunSQL(SQL_ADD_CONSTRAINT),
        migrations.RunSQL(SQL_ADD_INDEX),
    ]
