"""
The django_orm source provides an interface for querying data from a table in
the database.

.. note::

    The database source requires Django to be installed and connected to
    your database.

The source intentionally does not do any joins for performance reasons.
Because the reports will often be run over very large data sets, we want to be
sure that running the reports is not prohibitively time-consuming or hogging
the database.

If you want to produce reports over multiple tables, the best option is
generally to pre-join the tables into one merged reporting table, and then
run the report over that. In "enterprise-ese" this is basically a `star-schema
table`_ in your database with an `ETL`_ process to populate your data into it.
The interwebs have plenty to say about this topic, so we'll leave this issue
in your capable hands.

.. _star-schema table: http://en.wikipedia.org/wiki/Star_schema
.. _ETL: http://en.wikipedia.org/wiki/Extract,_transform,_load

If a whole new reporting database table is too heavy-handed for your use case,
there are a couple of simpler options. Often all you want is to pull in a bit
of data from another table, which you can do with the :class:`Lookup` column.
You can also use the :doc:`/sources/merge` to combine the results of two or
more reports over two or more database tables.

When using columns from the django_orm source, you'll be expected to provide
an extra report attribute to specify which model to pull the data from:

* ``django_model``: This report attribute specifies the database table to
  query. It should be specified as a dotted-path string pointing to a Django
  ``Model`` subclass. For example::
  
      django_model = 'project.app.models.ReportInfluencer'

"""

from collections import defaultdict
import heapq
import itertools

from django.db import models
from django.db.models.aggregates import Aggregate
from django.db.models.sql.aggregates import Aggregate as SQLAggregate

from blingalytics import sources


QUERY_LIMIT = 1000

class DjangoORMSource(sources.Source):
    def __init__(self, report):
        super(DjangoORMSource, self).__init__(report)
        self.set_django_model(report.django_model)

    def set_django_model(self, model):
        # Receive the django model class from the report definition.
        module, name = model.rsplit('.', 1)
        module = __import__(module, globals(), locals(), [name])
        self._model = getattr(module, name)

    def _query_filters(self):
        # Organize the QueryFilters by the columns they apply to.
        key_columns = set(dict(self._keys).keys())
        filtered_columns = set()
        query_filters = defaultdict(list)

        for name, report_filter in self._filters:
            if isinstance(report_filter, QueryFilter):
                if report_filter.columns:
                    if report_filter.columns & filtered_columns:
                        raise ValueError('You cannot include the same column '
                            'in more than one sqlalchemy filter.')
                    elif report_filter.columns & key_columns:
                        raise ValueError('You cannot filter key columns '
                            'since they are used in every filter query. '
                            'Maybe you could try a report-wide filter.')
                    else:
                        filtered_columns |= report_filter.columns
                query_filters[report_filter.columns].append(report_filter)

        # Determine the list of unfiltered sqlalchemy columns
        # (Exclude lookup columns)
        query_columns = [
            name for name, column in self._columns
            if isinstance(column, DjangoORMColumn)
        ]
        unfiltered_columns = frozenset(query_columns) \
            - filtered_columns - key_columns
        if unfiltered_columns:
            query_filters[unfiltered_columns] = []

        return query_filters

    def _perform_lookups(self, staged_rows):
        ###
        return staged_rows

    def _queries(self, clean_inputs):
        # Provides a list of iterators over the required queries, filtered
        # appropriately, and ensures each row is emitted with the proper
        # formatting: ((key), {row})
        key_column_names = map(lambda a: a[0], self._keys)
        model = self._model
        queries = []

        # Create a query object for each set of report filters
        query_filters_by_columns = self._query_filters()
        table_wide_filters = query_filters_by_columns.pop(None, [])

        # Ensure we do a query even if we have no non-key columns (odd but possible)
        query_filters_by_columns = query_filters_by_columns.items() or [([], [])]

        for column_names, query_filters in query_filters_by_columns:
            # Column names need to be a list to guarantee consistent ordering
            filter_column_names = key_column_names + list(column_names)
            query_columns = []
            query_modifiers = []
            query_group_bys = []

            # Collect the columns, modifiers, and group-bys
            query_names = {}
            for name in filter_column_names:
                column = self._columns_dict[name]
                query_group_by, query_name = column.get_query_group_bys(model)
                query_group_bys += query_group_by
                if query_name:
                    query_names[query_name] = name
                query_column, query_name = column.get_query_columns(model)
                query_columns += query_column
                if query_name:
                    query_names[query_name] = name
                query_modifiers += column.get_query_modifiers(model)

            # Construct the query
            q = model.objects.values(*query_group_bys)
            q = q.order_by(*query_group_bys)
            for query_modifier in query_modifiers:
                q = query_modifier(q)
            for query_filter in itertools.chain(table_wide_filters, query_filters):
                filter_arg = query_filter.get_filter(model, clean_inputs)
                if filter_arg:
                    q = q.filter(**dict([filter_arg]))
            q = q.annotate(*query_columns)

            # Set up iteration over the query, with formatted rows
            # (using generator here to make a closure for filter_column_names)
            def rows(q, filter_column_names):
                for row in _query_iterator(q):
                    yield dict([(query_names[k], v) for k, v in row.items()])
            queries.append(itertools.imap(
                lambda row: (tuple(row[name] for name, _ in self._keys), row),
                rows(q, filter_column_names)
            ))

        return queries

    def get_rows(self, key_rows, clean_inputs):
        # Merge the queries for each filter and do bulk lookups
        current_row = None
        current_key = None
        staged_rows = []
        for key, partial_row in heapq.merge(key_rows, *self._queries(clean_inputs)):
            if current_key and current_key == key:
                # Continue building the current row
                current_row.update(partial_row)
            else:
                if current_key is not None:
                    # Done with the current row, so stage it
                    staged_rows.append((current_key, current_row))
                    if len(staged_rows) >= QUERY_LIMIT:
                        # Do bulk table lookups on staged rows and emit them
                        finalized_rows = self._perform_lookups(staged_rows)
                        for row in finalized_rows:
                            yield row
                        staged_rows = []
                # Start building the next row
                current_key = key
                current_row = partial_row

        # Do any final leftover lookups and emit
        if current_row is not None:
            staged_rows.append((current_key, current_row))
            finalized_rows = self._perform_lookups(staged_rows)
            for row in finalized_rows:
                yield row

def _query_iterator(query, page=1000):
    # Pages over the results of a Django ORM query without loading everything
    # into memory at once
    start = 0
    while True:
        for i, result in enumerate(query.all()[start:start + page]):
            yield result
        if i < page - 1:
            break
        start += page

class QueryFilter(sources.Filter):
    """
    Filters the database query or queries for this report.

    This filter expects one positional argument, a function defining the
    filter operation. This function will be passed as its first argument the
    ``Model`` object. If a widget is defined for this filter, the function
    will also be passed a second argument, which is the user input value. The
    function should return a two-tuple whose first item is the filtering
    parameter (what would be the keyword argument to Model.objects.filter) and
    the second being the value to filter on. Or, based on the user input, the
    filter function can return ``None`` to indicate that no filtering should
    be done.

    You will generally build these in a lambda like so::

        django_orm.QueryFilter(lambda model: ('is_active', True))

    Or, with a user input widget::

        django_orm.QueryFilter(
            lambda model, user_input: ('user_id__in', user_input),
            widget=Autocomplete(multiple=True))

    """
    def __init__(self, filter_func, **kwargs):
        self.filter_func = filter_func
        super(QueryFilter, self).__init__(**kwargs)

    def get_filter(self, model, clean_inputs):
        # Applies the filter function to the model to return the filter.
        if self.widget:
            user_input = clean_inputs[self.widget._name]
            return self.filter_func(model, user_input)
        return self.filter_func(model)

class DjangoORMColumn(sources.Column):
    """
    Base class for a django_orm report column.
    """
    source = DjangoORMSource

    def __init__(self, field_name, **kwargs):
        self.field_name = field_name
        super(DjangoORMColumn, self).__init__(**kwargs)

    def get_query_columns(self, model):
        # Returns a list of model field names to query for.
        return [], None

    def get_query_modifiers(self, model):
        # Returns a list of functions to modify the query object.
        return []

    def get_query_group_bys(self, model):
        # Returns a list of group-by Entity.columns for the query.
        return [], None

# class Lookup(sources.Column):
#     """
#     This column allows you to "cheat" on the no-joins rule and look up a value
#     from an arbitrary database table by primary key.
# 
#     This column expects several positional arguments to specify how to do the
#     lookup:
# 
#     * The Elixir ``Entity`` object to look up from, specified as a
#       dotted-string reference.
#     * A string specifying the column attribute on the ``Entity`` you want to
#       look up.
#     * The name of the column in the report which is the primary key to use for
#       the lookup in this other table.
# 
#     The primary key name on the lookup table is assumed to be 'id'. If it's
#     different, you can use the keyword argument:
#     
#     * ``pk_attr``: The name of the primary key column in the lookup database
#       table. Defaults to ``'id'``.
# 
#     For example::
# 
#         database.Lookup('project.models.Publisher', 'name', 'publisher_id',
#             format=formats.String)
# 
#     Because the lookups are only done by primary key and are bulked up into
#     just a few operations, this isn't as taxing on the database as it could
#     be. But doing a lot of lookups on large datasets can get pretty
#     resource-intensive, so it's best to be judicious.
#     """
#     source = DjangoORMSource
# 
#     def __init__(self, model, lookup_field, pk_column, pk_field='id', **kwargs):
#         super(Lookup, self).__init__(**kwargs)
#         module, name = model.rsplit('.', 1)
#         module = __import__(module, globals(), locals(), [name])
#         self.model = getattr(module, name)
#         self._lookup_field = lookup_field
#         self._pk_field = pk_field
#         self.pk_column = pk_column
# 
#     @property
#     def lookup_attr(self):
#         return (self.model, self._lookup_field)
# 
#     @property
#     def pk_attr(self):
#         return (self.model, self._pk_field)

class GroupBy(DjangoORMColumn):
    """
    Performs a group-by operation on the given database column. It takes one
    positional argument: a string specifying the column to group by. There is
    also an optional keyword argument:

    * ``include_null``: Whether the database column you're grouping on should
      filter out or include the null group. Defaults to ``False``, which will
      not include the null group.

    Any group-by columns should generally be listed in your report's keys.
    You are free to use more than one of these in your report, which will be
    treated as a multi-group-by operation in the database.

    This column does not compute or output a footer.
    """
    def __init__(self, field_name, include_null=False, **kwargs):
        self.include_null = include_null
        super(GroupBy, self).__init__(field_name, **kwargs)

    def get_query_modifiers(self, model):
        # If we're removing the null grouping, filter it out
        if not self.include_null:
            filters = {'%s__isnull' % self.field_name: False}
            return [lambda q: q.filter(**filters)]
        return []

    def get_query_group_bys(self, model):
        return [self.field_name], self.field_name

    def increment_footer(self, total, cell):
        # Never return a footer
        return None

    def finalize_footer(self, total, footer):
        # Never return a footer
        return None

class Sum(DjangoORMColumn):
    """
    Performs a database sum aggregation. The first argument should be a string
    specifying the model field to sum.
    """
    def get_query_columns(self, model):
        return [models.Sum(self.field_name)], '%s__sum' % self.field_name

class Count(DjangoORMColumn):
    """
    Performs a database count aggregation. The first argument should be a
    string specifying the database column to count on. This also accepts one
    extra keyword argument:

    * ``distinct``: Whether to perform a distinct count or not. Defaults to
      ``False``.
    """
    def __init__(self, field_name, distinct=False, **kwargs):
        self._distinct = bool(distinct)
        super(Count, self).__init__(field_name, **kwargs)

    def get_query_columns(self, model):
        return ([models.Count(self.field_name, distinct=self._distinct)],
            '%s__count' % self.field_name)

class First(DjangoORMColumn):
    """
    .. note::

        Using this column requires that your database have a ``first``
        aggregation function. In many databases, you will have to add this
        aggregate yourself. For example, here is a
        `PostgreSQL implementation`_.

    .. _PostgreSQL implementation: http://wiki.postgresql.org/wiki/First_(aggregate)
    
    Performs a database first aggregation. The first argument should be a
    string specifying the database column to operate on.
    """
    def get_query_columns(self, model):
        return [FirstAggregate(self.field_name)], '%s__first' % self.field_name

class Max(DjangoORMColumn):
    """
    Performs a database max aggregation. The first argument should be a string
    specifying the database column to find the max of.
    """
    def get_query_columns(self, model):
        return [models.Max(self.field_name)], '%s__max' % self.field_name

class Min(DjangoORMColumn):
    """
    Performs a database min aggregation. The first argument should be a string
    specifying the database column to find the min of.
    """
    def get_query_columns(self, model):
        return [models.Min(self.field_name)], '%s__min' % self.field_name

class Avg(DjangoORMColumn):
    """
    Performs a database average aggregation. The first argument should be a
    string specifying the database column to average.
    """
    def get_query_columns(self, model):
        return [models.Avg(self.field_name)], '%s__avg' % self.field_name

# class TableKeyRange(sources.KeyRange):
#     """
#     This key range ensures that there is a key for every row in the given
#     database table. This is primarily useful to ensure that you get every row
#     ID from an external table in your report.
# 
#     This key range takes one positional argument, a dotted-string reference to
#     the ``Entity`` to pull from. It also takes two optional keyword arguments:
#     
#     * ``pk_column``: The column name for the primary key to use from the
#       table. Defaults to ``'id'``.
#     * ``filters``: Either a single filter or a list of filters. These filters
#       will be applied when pulling the keys from this database table.
#     """
#     def __init__(self, entity, pk_column='id', filters=[]):
#         module, name = entity.rsplit('.', 1)
#         module = __import__(module, globals(), locals(), [name])
#         self.entity = getattr(module, name)
#         self._pk_column = pk_column
#         if isinstance(filters, sources.Filter):
#             self.filters = [filters]
#         else:
#             self.filters = filters
# 
#     @property
#     def pk_column(self):
#         return getattr(self.entity, self._pk_column)
# 
#     def get_row_keys(self, clean_inputs):
#         # Query for the primary keys
#         q = elixir.session.query(self.pk_column)
# 
#         # Apply the filters to the query
#         for query_filter in self.filters:
#             filter_arg = query_filter.get_filter(self.entity, clean_inputs)
#             if filter_arg is not None:
#                 q = q.filter(filter_arg)
#         q = q.order_by(self.pk_column)
# 
#         # Return the ids
#         return itertools.imap(
#             lambda row: row[0],
#             q.yield_per(QUERY_LIMIT)
#         )


# For construction of custom aggregate, see the following:
# http://groups.google.com/group/django-users/browse_thread/thread/bd5a6b329b009cfa
# https://code.djangoproject.com/browser/django/trunk/django/db/models/aggregates.py#L26
# https://code.djangoproject.com/browser/django/trunk/django/db/models/sql/aggregates.py
class FirstAggregate(Aggregate):
    name = 'First'
    def add_to_query(self, query, alias, col, source, is_summary):
        aggregate = SQLFirstAggregate(col, source=source, is_summary=is_summary, **self.extra)
        query.aggregates[alias] = aggregate

class SQLFirstAggregate(SQLAggregate):
    sql_function = 'FIRST'
