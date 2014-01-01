import os

from fabric.api import local
from fabric.context_managers import hide, settings


def test():
    """Runs the blingalytics test suite."""
    path = os.path.dirname(os.path.realpath(__file__))
    os.environ['PYTHONPATH'] = path
    with settings(hide('warnings'), warn_only=True):
        local('python test/test_runner.py')


def update_pypi():
    """Updates versions and packages for PyPI."""
    # - update version in setup.py
    # - update version in docs/conf.py
    # - git tag -a vx.y.z -m "vx.y.z"
    # - git push origin master --tags
    # - python setup.py register
    # - python setup.py sdist upload
    #     (cannot be in vagrant shared directory -- copy contents to tmp)
