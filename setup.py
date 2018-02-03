from setuptools import setup
import os


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
HISTORY = open(os.path.join(here, 'HISTORY.rst')).read()


version = "1.5.1"


setup(
    version=version,
    description="Plugin for ploy to provision FreeBSD jails using ezjail.",
    long_description=README + "\n\n" + HISTORY,
    name="ploy_ezjail",
    author='Florian Schulze',
    author_email='florian.schulze@gmx.net',
    license="BSD 3-Clause License",
    url='http://github.com/ployground/ploy_ezjail',
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Systems Administration'],
    include_package_data=True,
    zip_safe=False,
    packages=['ploy_ezjail'],
    install_requires=[
        'setuptools',
        'ploy >= 1.2.0, < 2dev',
        'lazy'],
    entry_points="""
        [ploy.plugins]
        ezjail = ploy_ezjail:plugin
    """)
