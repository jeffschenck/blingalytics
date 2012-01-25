from decimal import Decimal
import unittest

from blingalytics import widgets
from blingalytics.sources import sqlalchemy_orm
from mock import Mock

from test import entities, reports


class TestSQLAlchemySource(unittest.TestCase):
    def setUp(self):
        entities.init_db_from_scratch()
        self.report = reports.BasicDatabaseReport(Mock())

    def test_sqlalchemy_source(self):
        source = sqlalchemy_orm.SQLAlchemySource(self.report)
        id1, id2 = entities.Compare(), entities.Compare()
        self.assertEqual(list(source.get_rows([], {'user_is_active': None})), [
            ((id1,), {'_sum_widget_price': Decimal('7.02'), 'user_id': 1, 'num_widgets': 3, 'user_is_active': True}),
            ((id2,), {'_sum_widget_price': Decimal('50.00'), 'user_id': 2, 'num_widgets': 1, 'user_is_active': False}),
        ])

    def test_sqlalchemy_key_ranges(self):
        # Straight up
        key_range = sqlalchemy_orm.TableKeyRange('test.entities.AllTheData', pk_column='widget_id')
        self.assertEqual(set(key_range.get_row_keys([])), set([1, 2, 3, 4]))
    
        # Now with filtering
        key_range = sqlalchemy_orm.TableKeyRange('test.entities.AllTheData', pk_column='widget_id',
            filters=sqlalchemy_orm.QueryFilter(lambda entity: entity.id > 2))
        self.assertEqual(set(key_range.get_row_keys({})), set([3, 4]))
    
    def test_sqlalchemy_filters(self):
        # ColumnTransform functionality
        self.assertRaises(ValueError, sqlalchemy_orm.ColumnTransform, lambda column: column.op('+')(1))
        fil = sqlalchemy_orm.ColumnTransform(lambda column: column.op('+')(1), columns=['plussed'])
        trans = fil.transform_column(entities.AllTheData.id, {}).compile()
        self.assertEqual(str(trans), 'all_the_data.id + :id_1')
        self.assertEqual(trans.params['id_1'], 1)
        widget = widgets.Select(choices=((1, '1'), (2, '2')))
        widget._name = 'widget'
        fil = sqlalchemy_orm.ColumnTransform(lambda column, user_input: column.op('+')(user_input), columns=['plussed'], widget=widget)
        trans = fil.transform_column(entities.AllTheData.id, {'widget': widget.clean(1)}).compile()
        self.assertEqual(str(trans), 'all_the_data.id + :id_1')
        self.assertEqual(trans.params['id_1'], 2)

        # QueryFilter functionality
        fil = sqlalchemy_orm.QueryFilter(lambda entity: entity.id < 10)
        query_filter = fil.get_filter(entities.AllTheData, {}).compile()
        self.assertEqual(str(query_filter), 'all_the_data.id < :id_1')
        self.assertEqual(query_filter.params['id_1'], 10)
        widget = widgets.Select(choices=(([1, 2, 3], 'Low'), ([4, 5, 6], 'High')))
        widget._name = 'widget'
        fil = sqlalchemy_orm.QueryFilter(lambda entity, user_input: entity.id.in_(user_input) if user_input else None, widget=widget)
        query_filter = fil.get_filter(entities.AllTheData, {'widget': widget.clean(0)}).compile()
        self.assertEqual(str(query_filter), 'all_the_data.id IN (:id_1, :id_2, :id_3)')
        self.assertEqual(set(query_filter.params.values()), set([1, 2, 3]))

    def test_sqlalchemy_columns(self):
        # Lookup functionality
        col = sqlalchemy_orm.Lookup('test.entities.AllTheData', 'user_id', 'widget_id')
        self.assertEqual(col.entity, entities.AllTheData)
        self.assert_(col.lookup_attr is entities.AllTheData.user_id)
        self.assert_(col.pk_attr is entities.AllTheData.id)
        self.assertEqual(col.pk_column, 'widget_id')
        col = sqlalchemy_orm.Lookup('test.entities.AllTheData', 'user_id', 'widget_id', 'widget_id')
        self.assert_(col.pk_attr is entities.AllTheData.widget_id)

        # GroupBy
        col = sqlalchemy_orm.GroupBy('user_id')
        self.assert_(col.get_query_column(entities.AllTheData) is entities.AllTheData.user_id)
        self.assertEqual(len(col.get_query_group_bys(entities.AllTheData)), 1)
        self.assert_(col.get_query_group_bys(entities.AllTheData)[0] is entities.AllTheData.user_id)
        self.assertEqual(col.increment_footer(None, 10), None)
        self.assertEqual(col.finalize_footer(None, {'othercolumn': 'string'}), None)

        # Sum
        col = sqlalchemy_orm.Sum('widget_price')
        self.assertEqual(
            str(col.get_query_column(entities.AllTheData).compile()),
            'sum(all_the_data.widget_price)')

        # Count
        col = sqlalchemy_orm.Count('user_id')
        self.assertEqual(
            str(col.get_query_column(entities.AllTheData).compile()),
            'count(all_the_data.user_id)')
        col = sqlalchemy_orm.Count('user_id', distinct=True)
        self.assertEqual(
            str(col.get_query_column(entities.AllTheData).compile()),
            'count(DISTINCT all_the_data.user_id)')

        # First
        col = sqlalchemy_orm.First('widget_id')
        self.assertEqual(
            str(col.get_query_column(entities.AllTheData).compile()),
            'first(all_the_data.widget_id)')

        # BoolAnd
        col = sqlalchemy_orm.BoolAnd('user_is_active')
        self.assertEqual(
            str(col.get_query_column(entities.AllTheData).compile()),
            'bool_and(all_the_data.user_is_active)')

        # BoolOr
        col = sqlalchemy_orm.BoolOr('user_is_active')
        self.assertEqual(
            str(col.get_query_column(entities.AllTheData).compile()),
            'bool_or(all_the_data.user_is_active)')

        # ArrayAgg
        col = sqlalchemy_orm.ArrayAgg('widget_id')
        self.assertEqual(
            str(col.get_query_column(entities.AllTheData).compile()),
            'array_agg(all_the_data.widget_id)')
