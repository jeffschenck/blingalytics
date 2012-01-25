from datetime import date

from blingalytics import base, formats, widgets
from blingalytics.sources import derived, key_range, merge, sqlalchemy_orm, static


ACTIVE_USER_CHOICES = (
    (None, 'All'),
    (True, 'Active'),
    (False, 'Inactive'),
)

class SuperBasicReport(base.Report):
    filters = []
    keys = ('id', key_range.EpochKeyRange(date(2011, 1, 1), date(2011, 1, 3)))
    columns = [
        ('id', static.Value(1, format=formats.Integer)),
    ]
    default_sort = ('id', 'desc')

class BasicDatabaseReport(base.Report):
    sqlalchemy_entity = 'test.entities.AllTheData'
    filters = [
        ('user_is_active', sqlalchemy_orm.QueryFilter(lambda entity, user_input: entity.user_is_active == user_input if user_input is not None else None,
            widget=widgets.Select(label='User Is Active', choices=ACTIVE_USER_CHOICES))),
    ]
    keys = ('user_id', key_range.SourceKeyRange)
    columns = [
        ('user_id', sqlalchemy_orm.GroupBy('user_id', format=formats.Integer(label='User ID', grouping=False))),
        ('user_is_active', sqlalchemy_orm.First('user_is_active', format=formats.Boolean(label='Active?'))),
        ('num_widgets', sqlalchemy_orm.Count('widget_id', distinct=True, format=formats.Integer(label='Widgets'))),
        ('_sum_widget_price', sqlalchemy_orm.Sum('widget_price')),
        ('average_widget_price', derived.Value(lambda row: row['_sum_widget_price'] / row['num_widgets'], format=formats.Bling)),
    ]
    default_sort = ('average_widget_price', 'desc')

class BasicMergeReport(base.Report):
    merged_reports = {
        'one': BasicDatabaseReport,
        'two': BasicDatabaseReport,
    }
    filters = [
        ('num_widgets', merge.PostFilter(lambda row: row['double_num_widgets'] > 0)),
        ('user_is_active', merge.DelegatedFilter(
            sqlalchemy_orm.QueryFilter(lambda entity, user_input: entity.user_is_active == user_input if user_input is not None else None),
            widget=widgets.Select(label='User Is Active', choices=ACTIVE_USER_CHOICES))),
        ('include', merge.ReportFilter('one',
            widget=widgets.Checkbox(label='Include', default=True))),
    ]
    keys = ('user_id', key_range.SourceKeyRange)
    columns = [
        ('user_id', merge.First(format=formats.Integer(label='ID', grouping=False), footer=False)),
        ('user_is_active', merge.First(format=formats.Boolean)),
        ('double_num_widgets', merge.Sum('num_widgets', format=formats.Integer)),
        ('single_num_widgets', derived.Value(lambda row: row['double_num_widgets'] / 2, format=formats.Integer)),
    ]
    default_sort = ('single_num_widgets', 'asc')
