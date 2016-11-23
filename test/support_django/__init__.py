from decimal import Decimal

from django.core.management import call_command
from django.db import connection
from django import setup


FIRST = [
    'DROP AGGREGATE IF EXISTS public.first(anyelement)',
    'DROP FUNCTION IF EXISTS public.first_agg(anyelement, anyelement)',
    '''
    CREATE OR REPLACE FUNCTION public.first_agg ( anyelement, anyelement )
    RETURNS anyelement AS $$
            SELECT $1;
    $$ LANGUAGE SQL IMMUTABLE STRICT
    ''',
    '''
    CREATE AGGREGATE public.first (
            sfunc    = public.first_agg,
            basetype = anyelement,
            stype    = anyelement
    )
    ''',
]


def init_db_from_scratch():
    """Build the necessary stuff in the db to run."""
    setup()
    call_command('flush', interactive=False, verbosity=0)
    call_command('migrate', interactive=False, verbosity=0)
    filler_data()


def add_first_db_function():
    """Adds a first function to the database."""
    cursor = connection.cursor()
    try:
        for statement in FIRST:
            cursor.execute(statement)
    finally:
        cursor.close()

def filler_data():
    from test.support_django.models import AllTheData
    datas = [
        {'user_id': 1, 'user_is_active': True, 'widget_id': 1, 'widget_price': Decimal('1.23')},
        {'user_id': 1, 'user_is_active': True, 'widget_id': 2, 'widget_price': Decimal('2.34')},
        {'user_id': 1, 'user_is_active': True, 'widget_id': 3, 'widget_price': Decimal('3.45')},
        {'user_id': 2, 'user_is_active': False, 'widget_id': 4, 'widget_price': Decimal('50.00')},
    ]
    for data in datas:
        obj = AllTheData(**data)
        obj.save()
