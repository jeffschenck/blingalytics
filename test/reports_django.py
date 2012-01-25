from blingalytics import base, formats, widgets
from blingalytics.sources import derived, key_range, django_orm


ACTIVE_USER_CHOICES = (
    (None, 'All'),
    (True, 'Active'),
    (False, 'Inactive'),
)

class BasicDatabaseReport(base.Report):
    django_model = 'test.support_django.models.AllTheData'
    filters = [
        ('user_is_active', django_orm.QueryFilter(lambda model, user_input: ('user_is_active', user_input) if user_input is not None else None,
            widget=widgets.Select(label='User Is Active', choices=ACTIVE_USER_CHOICES))),
    ]
    keys = ('user_id', key_range.SourceKeyRange)
    columns = [
        ('user_id', django_orm.GroupBy('user_id', format=formats.Integer(label='User ID', grouping=False))),
        ('user_is_active', django_orm.First('user_is_active', format=formats.Boolean(label='Active?'))),
        ('num_widgets', django_orm.Count('widget_id', distinct=True, format=formats.Integer(label='Widgets'))),
        ('_sum_widget_price', django_orm.Sum('widget_price')),
        ('average_widget_price', derived.Value(lambda row: row['_sum_widget_price'] / row['num_widgets'], format=formats.Bling)),
    ]
    default_sort = ('average_widget_price', 'desc')
