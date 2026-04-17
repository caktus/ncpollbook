from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ncsbe", "0002_auto_20260324_1256"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                # Wrapped in a DO block so the migration silently skips if the
                # materialized views don't exist yet (e.g. fresh test database
                # before sync_pgviews has run).
                """
                DO $$ BEGIN
                    CREATE INDEX IF NOT EXISTS voter_view_county_name_idx
                        ON ncsbe_voterview (county_name);
                EXCEPTION WHEN undefined_table THEN NULL;
                END $$;
                """,
                """
                DO $$ BEGIN
                    CREATE INDEX IF NOT EXISTS voter_event_view_ncid_idx
                        ON ncsbe_votereventview (ncid);
                EXCEPTION WHEN undefined_table THEN NULL;
                END $$;
                """,
            ],
            reverse_sql=[
                "DROP INDEX IF EXISTS voter_view_county_name_idx;",
                "DROP INDEX IF EXISTS voter_event_view_ncid_idx;",
            ],
        ),
    ]
