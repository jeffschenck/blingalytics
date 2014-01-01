import os
import re

from fabric.api import hide, lcd, local, prompt, settings


PROJECT_PATH = os.path.dirname(os.path.realpath(__file__))


def test():
    """Runs the blingalytics test suite."""
    os.environ['PYTHONPATH'] = PROJECT_PATH
    with settings(hide('warnings'), warn_only=True):
        local('python test/test_runner.py')


def update_pypi():
    """Updates versions and packages for PyPI."""
    # Verify that we want to do this...
    sure = prompt('Are you sure you want to release a new version to PyPI? '
        'Have you pushed all changes to origin/master? [y/n]',
        validate=r'^[yYnN]')
    if sure.lower()[0] != 'y':
        return

    # First update version numbers
    with lcd(PROJECT_PATH):
        old_version = local('grep version= setup.py', capture=True)
    old_version = re.search(r'\'([0-9a-zA-Z.]+)\'', old_version).group(1)
    new_version = prompt(
        'What version number (previous: {0})?'.format(old_version),
        validate=r'^\d+\.\d+\.\d+\w*$')
    local('sed -i -r -e "s/{before}/{after}/g" {filename}'.format(
        filename=os.path.join(PROJECT_PATH, 'setup.py'),
        before=r"version='[0-9a-zA-Z.]+'",
        after="version='{0}'".format(new_version)))
    local('sed -i -r -e "s/{before}/{after}/g" {filename}'.format(
        filename=os.path.join(PROJECT_PATH, 'docs', 'conf.py'),
        before=r"version = '[0-9]+\.[0-9]+'",
        after="version = '{0}'".format('.'.join(new_version.split('.')[:2]))))
    local('sed -i -r -e "s/{before}/{after}/g" {filename}'.format(
        filename=os.path.join(PROJECT_PATH, 'docs', 'conf.py'),
        before=r"release = '[0-9]+\.[0-9]+\.[0-9a-zA-Z]+'",
        after="release = '{0}'".format(new_version)))

    # Then tag and push to git
    local('git tag -f -a v{0} -m "v{0}"'.format(new_version))
    local('git push origin master --tags')

    # Register new version on PyPI
    # Note: copy to /tmp because vagrant shared directories don't handle
    #       links well, which are part of the sdist process
    local('cp -r {0} /tmp/'.format(PROJECT_PATH))
    with lcd('/tmp/blingalytics'):
        local('python setup.py register')
        local('python setup.py sdist upload')
