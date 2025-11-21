from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('myapp', '0004_fix_missing_has_rebate'),
    ]

    operations = [
        migrations.RunSQL(
            sql=r'''
            -- Add missing columns to myapp_customerhistory if they don't exist (PostgreSQL)
            DO $$
            BEGIN
                -- item_name
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'myapp_customerhistory' AND column_name = 'item_name'
                ) THEN
                    ALTER TABLE myapp_customerhistory
                    ADD COLUMN item_name varchar(255) NOT NULL DEFAULT '';
                END IF;

                -- item_model
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'myapp_customerhistory' AND column_name = 'item_model'
                ) THEN
                    ALTER TABLE myapp_customerhistory
                    ADD COLUMN item_model varchar(255) NOT NULL DEFAULT '';
                END IF;

                -- transaction_number
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'myapp_customerhistory' AND column_name = 'transaction_number'
                ) THEN
                    ALTER TABLE myapp_customerhistory
                    ADD COLUMN transaction_number varchar(50);
                END IF;

                -- term
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'myapp_customerhistory' AND column_name = 'term'
                ) THEN
                    ALTER TABLE myapp_customerhistory
                    ADD COLUMN term integer NOT NULL DEFAULT 0;
                END IF;

                -- completed_by_id (FK to myapp_customuser)
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'myapp_customerhistory' AND column_name = 'completed_by_id'
                ) THEN
                    ALTER TABLE myapp_customerhistory
                    ADD COLUMN completed_by_id integer NULL;

                    -- Add FK if users table exists (ignore errors if already present)
                    BEGIN
                        ALTER TABLE myapp_customerhistory
                        ADD CONSTRAINT myapp_customerhistory_completed_by_id_fk
                        FOREIGN KEY (completed_by_id)
                        REFERENCES myapp_customuser (id)
                        DEFERRABLE INITIALLY DEFERRED;
                    EXCEPTION WHEN duplicate_object THEN
                        -- constraint already exists
                        NULL;
                    END;
                END IF;
            END$$;
            ''',
            reverse_sql=r'''
            -- This migration is non-destructive; no reverse action.
            ''',
        )
    ]
