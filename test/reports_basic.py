from datetime import date

from blingalytics import base, formats
from blingalytics.sources import key_range, static


class SuperBasicReport(base.Report):
    filters = []
    keys = ('id', key_range.EpochKeyRange(date(2011, 1, 1), date(2011, 1, 3)))
    columns = [
        ('id', static.Value(1, format=formats.Integer)),
    ]
    default_sort = ('id', 'desc')
