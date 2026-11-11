`0001_initial_schema` creates the approved five schemas, 17 tables, indexes,
constraints, pgcrypto extension, timestamp function, ten triggers and comments.
The revision is frozen and does not import application models or read design files.

Upgrade expects an empty domain schema. An existing `public.set_updated_at()`
function causes an error rather than overwriting a potentially unrelated function.
Alembic owns the transaction so a failed upgrade rolls back its schema changes.

Downgrade permanently deletes all domain tables and data, then the timestamp
function and the five schemas. It never uses DROP CASCADE; unrelated dependencies
or objects block the downgrade. pgcrypto is retained because it may be shared.
Only run downgrade against disposable databases or after explicitly approving
the loss of domain data. Integration tests use newly created, randomly named
databases and perform upgrade, downgrade and upgrade again there.
