Overview
========

The ploy_ezjail plugin provides integration of `ezjail`_ with `ploy`_ to manage `FreeBSD`_ jails.

.. _ezjail: http://erdgeist.org/arts/software/ezjail/
.. _ploy: https://github.com/ployground/
.. _FreeBSD: http://www.freebsd.org


Installation
============

ploy_ezjail is best installed with easy_install, pip or with zc.recipe.egg in a buildout.


Masters
=======

To use ploy_ezjail you need a host running FreeBSD on which you want to manage jails.

You declare a master with ``[ez-master:masterid]`` where ``masterid`` is the name you want to use for this master.
Now you can either add options like for a ``plain`` ploy instance, or you can use the ``instance`` option to refer to another instance from your config like this::

    [ez-master:master1]
    host = myhost.example.com

    [plain-instance:foohost]
    host = foohost.example.com

    [ez-master:master2]
    instance = foohost

The latter is most useful in conjunction with other ploy backend plugins, as it allows you to easily switch between provisioners, i.e. to have an ``ez-master`` provisioned on VirtualBox during development and on a ``plain`` instance in production.


Options
-------

``debug-commands``
  If set to ``yes``, the commands executed on the host are echoed locally.

``instance``
  The instance to use as host for this master.

``ezjail-admin``
  Path to the ``ezjail-admin`` script on the host.
  Defaults to ``/usr/local/bin/ezjail-admin``.

``sudo``
  Use ``sudo`` to run commands on the host.


Instances
=========

At the moment all jails will be created using ZFS (the ``-c zfs`` option of ``ezjail-admin``), so the host needs to be setup accordingly.


Options
-------

``ip``
  The ip address to use for the jail.
  **Required**

``flavour``
  The **flavour** to use for this jail. This is explained in the `ezjail docs <http://erdgeist.org/arts/software/ezjail/>`_.

``mounts``
  Additional mount points for the jail.
  You can specify one mount point per line.
  The format is::

      src=SRC dst=DST [ro=true] [create=true]

  The ``src`` is the path on the host, ``dst`` is the path inside the jail.

  If ``ro`` is set to ``true``, then the mount is read only.

  When ``create`` is enabled, then the ``src`` path is created with ``mkdir -p``.
  The ``dst`` path is always created inside the jail with ``mkdir -p``.

  You can reference `ZFS sections`_ inside ``src`` with ``{zfs[name]}`` where ``name`` is the ``ez-zfs`` section name.
  You can use the name of the jail instance with ``{name}}`` in both ``src`` and ``dst``.
  Examples::

      src=/foo dst=/foo
      src={zfs[backup]} dst=/bak
      src={zfs[data]}/{name} dst=/mnt/data create=true
      src={zfs[static]} dst=/mnt/static ro=true

``no-terminate``
  If set to ``yes``, the jail can't be terminated via ploy until the setting is changed to ``no`` or removed entirely.

``startup_script``
  Path to a local script (relative to the location of the configuration file) which will be run inside the jail right after creation and first start of the jail.


ZFS sections
============

You can specify ZFS filesystems via ``[ez-zfs:name]`` sections.
This is used in mounts of jails to get the mountpoint and verify that the path exists and is it's own ZFS filesystem.
You can also create new ZFS filesystems with the ``create`` option.


Options
-------

``create``
  If set to ``yes``, the filesystem is created when first used.

``path``
  Specifies the path of this filesystem.
  This is not the mountpoint, but the ZFS path.
  You can reference other ZFS sections with ``{zfs[name][path]}``.
  The ``name`` is the name of the referenced ZFS section.
  The ``[path]`` at the end is mandatory, as otherwise you would get the mountpoint of the referenced ZFS section.
  Examples::

    [ez-zfs:data]
    path = tank/data

    [ez-zfs:shared]
    path = {zfs[data][path]}/shared

    [ez-zfs:jails]
    path = {zfs[data][path]}/jails

    [ez-zfs:backup]
    create = true
    path = tank/backup


Changelog
=========

1.0.1 - Unreleased
------------------

* Use new helper in ploy 1.0.2 to setup proxycommand.
  [fschulze]


1.0.0 - 2014-07-19
------------------

* Added documentation.
  [fschulze]


1.0b9 - 2014-07-08
------------------

* Packaging and test fixes.
  [fschulze]


1.0b8 - 2014-07-04
------------------

* Python 3 compatibility.
  [fschulze]

* Renamed mr.awsome to ploy and mr.awsome.ezjail to ploy_ezjail.
  [fschulze]


1.0b7 - 2014-06-16
------------------

* Provide default values for ``proxyhost`` and ``proxycommand`` options.
  [fschulze]

* Merge config of ez-master with the instance it's using.
  [fschulze]


1.0b6 - 2014-06-11
------------------

* Pass changes of proxy instance config on to the proxied instance config.
  [fschulze]


1.0b5 - 2014-06-10
------------------

* Forcefully destroy jail. Together with ezjail 3.4.1 this solves the issue
  that sometimes the ZFS filesystem wasn't removed and the jail couldn't be
  started without manual intervention.
  [fschulze]


1.0b4 - 2014-05-22
------------------

* Clear out massagers after copying the config for the proxy instance to
  prevent conflicts when the proxy instance is created.
  [fschulze]


1.0b3 - 2014-05-21
------------------

* Fixes to make ``[instance:...]`` using an ez-master work.
  [fschulze]


1.0b2 - 2014-05-15
------------------

* Added ``instance`` option to ez-master section to use another instance as
  the jail host.
  [fschulze, tomster]

* Moved setuptools-git from setup.py to .travis.yml, it's only needed for
  releases and testing.
  [fschulze]


1.0b1 - 2014-03-24
------------------

* Initial release
  [fschulze]
