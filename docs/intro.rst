Sweet walkthrough
=================

This intro should get you up and running with a basic Blingalytics
installation in just a few minutes. Once you're done, you can check out the
documentation for :doc:`sources` and :doc:`caches` to contemplate your options
for snappier infrastructure.

If you haven't done so yet, you'll need to install the ``blingalytics``
package and requirements before beginning. See :doc:`install` for details.

One: define a report
--------------------

With Blingalytics, you use a "report" definition to describe precisely what
data you want to look at and how you want to slice it. In a report definition,
you're only required to do two things:

* List the output columns and where they should get their data
* Define the key range for the report (explained below)

Baby's first report
^^^^^^^^^^^^^^^^^^^

So to start, let's put together a completely useless simplest-case report::

    from blingalytics import base, formats
    from blingalytics.sources import key_range, static

    class LameReport(base.Report):
        keys = ('lame', key_range.SourceKeyRange)
        columns = [
            ('lame', static.Value(5, format=formats.Integer)),
        ]

So what does this report do? It provides one output column, whose value will
always be ``5``. However, that's not even the most useless property of this
report, as this report will actually return zero rows. This is why a report's
keys matter.

Key concept
^^^^^^^^^^^

The keys for a report determine what rows will be in the output. If your
website sells doodads, you might want to see how many doodads you sell per
day. In this case, the report keys would be the range of days you report on so
that you get one row per day. If, on the other hand, you want to see how many
doodads each user has bought, you would want one row per user. So the user ID
is your report key, and the range would be all your users.

To specify the key range for your report, you set the keys attribute of your
report class to a two-tuple. The first item is the label of your key column,
and the second item is the type of key range. In our example, the
:class:`sources.SourceKeyRange <blingalytics.sources.SourceKeyRange>` tells
the report to only include rows returned by the source data. Other key ranges,
such as a range of days, can be used to ensure that a row is returned for each
key, even if there is no source data.

For advanced use cases, you can even have compound keys. For example, you
could have a row per user per day. See :doc:`/reports` for more.

Build your columns
^^^^^^^^^^^^^^^^^^

Columns are defined in a report as a list of two-tuples. Each two-tuple
represents a column, in order, by defining a label and its data source. The
label should be unique among the columns, and is used by keys and other
options to reference that column. The data source defines how that column's
data should be computed, and is covered in more detail in :doc:`/sources`.

A slightly realer report
^^^^^^^^^^^^^^^^^^^^^^^^

Now that we know a bit more about how this works, let's define a report that
actually does something (to be fair, it's still pretty useless, but we're
getting closer)::

    from blingalytics import base, formats
    from blingalytics.sources import derived, key_range, static

    class RealerReport(base.Report):
        keys = ('prime', key_range.IterableKeyRange([2, 3, 5, 7, 11, 13, 17]))
        columns = [
            ('prime', key_range.Value(format=formats.Integer)),
            ('squared', derived.Value(lambda row: row['prime'] ** 2, format=formats.Integer)),
            ('note', static.Value('Useful data coming soon...', format=formats.String)),
        ]
        default_sort = ('prime', 'asc')

So now we've got a report with three columns: prime is one of the prime
numbers from the key range; note is simply a static string value; and squared
is the square of the prime number. OK, time to run it!

Two: run the report
----------------------

Once you've defined a report, such as ``RealerReport``, you can instantiate
the report and tell it where to cache the data::

    from blingalytics.caches.local_cache import LocalCache
    report = RealerReport(LocalCache())

Once you have a report instance, you can run the report::

    report.run_report()

Retrieving report rows
^^^^^^^^^^^^^^^^^^^^^^

Now that the report is cached, you can retrieve the data with limits, offsets,
column sorting, and so on. But in the simplest case, you can just get all the
rows::

    rows = report.report_rows()
    # rows = [
    #    [1, '2', '4', 'Useful data coming soon...'],
    #    [2, '3', '9', 'Useful data coming soon...'],
    #    [3, '5', '25', 'Useful data coming soon...'],
    #    [4, '7', '49', 'Useful data coming soon...']]
    #    [5, '11', '121', 'Useful data coming soon...'],
    #    [6, '13', '169', 'Useful data coming soon...'],
    #    [7, '17', '289', 'Useful data coming soon...'],
    # ]

Let's try sorting and limiting the data::

    rows = report.report_rows(sort=('squared', 'asc'), limit=3)
    # rows = [
    #    [7, '17', '289', 'Useful data coming soon...'],
    #    [6, '13', '169', 'Useful data coming soon...'],
    #    [5, '11', '121', 'Useful data coming soon...'],
    # ]

There are plenty more options for retrieving specific rows. See
:meth:`Report.report_rows <blingalytics.base.Report.report_rows>` for more.

Three: put it in the browser
----------------------------

Working in the Python interpreter is nice and all, but most of us want to
insert this thing into a beautiful website and spread it around the web. Good
news! Blingalytics comes with the tools to pull this off in just a few lines
of code. (For example purposes, this will be shown as a Flask_ app, but it
should be easy enough to insert this into your favorite Python web framework.)

The report app
^^^^^^^^^^^^^^

Let's assume you've already :doc:`installed Blingalytics </install>` and
`installed Flask`_.

Now we build a very basic Flask app that has two URLs: a homepage, where we'll
display our report; and an AJAX responder for our report JavaScript to talk
to. The :func:`report_response <blingalytics.helpers.report_response>` helper
function makes responding to the AJAX requests easy.

::

    from blingalytics.helpers import report_response
    from flask import Flask, request, render_template
    from reports import RealerReport # import so it gets registered

    app = Flask(__name__)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/report/')
    def report():
        return report_response(request.args)

    if __name__ == '__main__':
        app.run(debug=True)

The ``index`` page really just renders the template where you're going to
implement the Blingalytics frontend. The ``report`` URL handles AJAX requests
from the JavaScript frontend, and the
:func:`report_response <blingalytics.helpers.report_response>` handles all the
dirty work of parsing request parameters and interfacing with your report
classes.

The report template
^^^^^^^^^^^^^^^^^^^

The template is even easier. Just include the appropriate CSS and JavaScript
on your page, and invoke the Blingalytics jQuery_ plugin:

.. code-block:: html

    <!DOCTYPE html>
    <html lang="en">
    <head>
      <link rel="stylesheet" href="/static/css/blingalytics.css" type="text/css" />
    </head>
    <body>
      <div id="report"></div>
      <script src="//ajax.googleapis.com/ajax/libs/jquery/1.6.2/jquery.min.js"></script>
      <script src="/static/js/jquery.dataTables.min.js"></script>
      <script src="/static/js/jquery.blingalytics.js"></script>
      <script>
        $('#report').blingalytics({
          'reportCodeName': 'realer_report'
        });
      </script>
    </body>
    </html>

With the CSS and JavaScript in place, you just have to pass in the
``'reportCodeName'`` option with the code name of the report you want to
display.

Partake in the beauty
^^^^^^^^^^^^^^^^^^^^^

That's it! Run your web app. For Flask, this involves running
``python app.py`` at the command line, where ``app.py`` is the app file you
created earlier. Then you should be able to point your browser to
``localhost:5000`` and play with the report in the browser.

Four: pull real data
---------------------

Be patient... coming soon.

.. .. note::
.. 
..     This section assumes you already have a database set up, using
..     SQLAlchemy and Elixir to connect and describe the tables. See
..     :doc:`/sources/sqlalchemy_orm` for details.

.. _Flask: http://flask.pocoo.org/
.. _installed Flask: http://flask.pocoo.org/docs/installation/
.. _jQuery: http://jquery.com/
