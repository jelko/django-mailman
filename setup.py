from setuptools import setup

setup(name = 'django-mailman',
    version = '0.5',
    packages = ['django_mailman',],
    platforms = ['any'],
    license = 'GNU LGPL v2.1',
    author = "Bernd Schlapsi",
    author_email = 'albert@albertoconnor.ca',
    description = 'Interface to Mailman Web-API',
    long_description = open('README.rst').read(),
    url = 'https://bitbucket.org/albertoconnor/django-mailman',
)
