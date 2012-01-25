from django.core.management import setup_environ
from test.support_django import settings
setup_environ(settings, 'test.support_django.settings')

from cStringIO import StringIO
from decimal import Decimal

from django.core.management import call_command


def init_db_from_scratch():
    """Build the necessary stuff in the db to run."""
    out = StringIO()
    call_command('flush', interactive=False, verbosity=0)
    call_command('syncdb', interactive=False, verbosity=0)
    filler_data()

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
