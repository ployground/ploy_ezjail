from setuptools import setup

version = "0.1"

setup(
    version=version,
    description="A plugin for mr.awsome providing support for FreeBSD jails using ezjail.",
    name="mr.awsome.ezjail",
    author='Florian Schulze',
    author_email='florian.schulze@gmx.net',
    url='http://github.com/fschulze/mr.awsome.ezjail',
    include_package_data=True,
    zip_safe=False,
    packages=['mr'],
    namespace_packages=['mr'],
    install_requires=[
        'setuptools',
        'mr.awsome >= 1.0dev',
    ],
    setup_requires=[
        'setuptools-git'],
    entry_points="""
        [mr.awsome.plugins]
        ezjail = mr.awsome_ezjail:plugin
    """)
