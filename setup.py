from setuptools import setup
import os


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()


version = "1.0b8"


setup(
    version=version,
    description="A plugin for ploy providing support for FreeBSD jails using ezjail.",
    long_description=README + "\n\n",
    name="ploy_ezjail",
    author='Florian Schulze',
    author_email='florian.schulze@gmx.net',
    license="BSD 3-Clause License",
    url='http://github.com/ployground/ploy_ezjail',
    include_package_data=True,
    zip_safe=False,
    packages=['ploy_ezjail'],
    install_requires=[
        'setuptools',
        'ploy >= 1.0rc10',
        'lazy'],
    entry_points="""
        [ploy.plugins]
        ezjail = ploy_ezjail:plugin
    """)
