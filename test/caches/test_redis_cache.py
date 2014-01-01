from datetime import datetime
from decimal import Decimal
import unittest

from blingalytics.caches import InstanceIncompleteError
from blingalytics.caches.redis_cache import RedisCache


REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379

CREATE_INSTANCE_ARGS = [
    'report_name',
    '123abc',
    [
        {'id': 1, 'name': 'Jeff', 'price': Decimal('1.50'), 'count': 40},
        {'id': 2, 'name': 'Tracy', 'price': Decimal('3.00'), 'count': 10},
        {'id': 3, 'name': 'Connie', 'price': Decimal('0.00'), 'count': 100},
        {'id': 4, 'name': 'Megan', 'price': None, 'count': -20},
    ],
    lambda: {'id': None, 'name': '', 'price': Decimal('4.50'), 'count': 32.5},
    86400,
]


class TestRedisCache(unittest.TestCase):
    def setUp(self):
        self.cache = RedisCache(host=REDIS_HOST, port=REDIS_PORT)
        self.cache.__enter__()
        self.cache.conn.flushall()

    def tearDown(self):
        self.cache.__exit__(None, None, None)

    def test_create_instance(self):
        self.cache.create_instance(*CREATE_INSTANCE_ARGS)
        self.assertEqual(
            set(self.cache.conn.keys()),
            set(['report_name:123abc:3', 'report_name:123abc:ids:', 'report_name:123abc:index:0:', 'report_name:123abc:_done:', 'report_name:123abc:1', 'report_name:123abc:', 'report_name:123abc:0', 'report_name:123abc:2', 'report_name:123abc:index:1:', 'report_name:123abc:index:2:', 'report_name:123abc:index:3:', 'report_name:123abc:footer:'])
        )

    def test_kill_cache(self):
        # Instance cache
        self.cache.create_instance(*CREATE_INSTANCE_ARGS)
        self.assertTrue(self.cache.conn.exists('report_name:123abc:'))
        self.cache.kill_instance_cache('report_name', '123abc')
        self.assertFalse(self.cache.conn.exists('report_name:123abc:'))

        # Report-wide cache
        self.cache.create_instance(*CREATE_INSTANCE_ARGS)
        self.assertTrue(self.cache.conn.exists('report_name:123abc:'))
        self.cache.kill_report_cache('report_name')
        self.assertFalse(self.cache.conn.exists('report_name:123abc:'))

    def test_instance_stats(self):
        # Before creating the instance in cache
        self.assertFalse(self.cache.is_instance_started('report_name', '123abc'))
        self.assertFalse(self.cache.is_instance_finished('report_name', '123abc'))
        self.assertRaises(InstanceIncompleteError, self.cache.instance_row_count, 'report_name', '123abc')
        self.assertRaises(InstanceIncompleteError, self.cache.instance_timestamp, 'report_name', '123abc')

        # After creating the instance in cache
        self.cache.create_instance(*CREATE_INSTANCE_ARGS)
        self.assertTrue(self.cache.is_instance_started('report_name', '123abc'))
        self.assertTrue(self.cache.is_instance_finished('report_name', '123abc'))
        self.assertEqual(self.cache.instance_row_count('report_name', '123abc'), 4)
        self.assertTrue(isinstance(self.cache.instance_timestamp('report_name', '123abc'), datetime))

    def test_instance_rows(self):
        self.cache.create_instance(*CREATE_INSTANCE_ARGS)

        rows = self.cache.instance_rows('report_name', '123abc',
            sort=('id', 'asc'), limit=2, offset=1)
        self.assertEqual(list(rows), [
            {'_bling_id': '1', 'id': 2, 'name': 'Tracy', 'price': Decimal('3.00'), 'count': 10},
            {'_bling_id': '2', 'id': 3, 'name': 'Connie', 'price': Decimal('0.00'), 'count': 100},
        ])

        rows = self.cache.instance_rows('report_name', '123abc',
            sort=('price', 'desc'), limit=None, offset=0)
        self.assertEqual(list(rows), [
            {'_bling_id': '1', 'id': 2, 'name': 'Tracy', 'price': Decimal('3.00'), 'count': 10},
            {'_bling_id': '0', 'id': 1, 'name': 'Jeff', 'price': Decimal('1.50'), 'count': 40},
            {'_bling_id': '2', 'id': 3, 'name': 'Connie', 'price': Decimal('0.00'), 'count': 100},
            {'_bling_id': '3', 'id': 4, 'name': 'Megan', 'price': None, 'count': -20},
        ])

    def test_instance_footer(self):
        self.assertRaises(InstanceIncompleteError, self.cache.instance_footer, 'report_name', '123abc')
        self.cache.create_instance(*CREATE_INSTANCE_ARGS)
        self.assertEqual(self.cache.instance_footer('report_name', '123abc'),
            CREATE_INSTANCE_ARGS[3]())
