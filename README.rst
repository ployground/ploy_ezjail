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
  If empty, the local machine is used without an ssh connection.

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

  This can either be a single IPv4 address::

      ip = 10.0.0.3

  or any number of IPv4 and IPv6 addresses attached to different devices::

      ip = lo1|10.0.0.3,vtnet0|2a03:b0c0:3:d0::3a4d:c002

  The latter format is `ezjail's<http://erdgeist.org/arts/software/ezjail/>`_ own.
  **Required**

``flavour``
  The **flavour** to use for this jail. This is explained in the `ezjail docs <http://erdgeist.org/arts/software/ezjail/>`_.

``ezjail-name``
  The **name** to use for the jail. By default the id of the instance is used.

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

``rc_require``
  String that indicates which other jails this jail requires to start up, effectively allowing you to define the startup order of jails.
  See ``rcorder(8)`` for more details.
  This value is written upon each startup of the jail not just when it is created initially, so to have changes take effect, it's sufficient to restart it.
  **Optional**

``rc_provide``
  String that indicates what this jail provides.
  ``ezjail`` itself always sets its jails to provide ``standard_ezjail`` to which ``ploy_ezjail`` adds the name of the jail.
  IOW if you simply want to build a startup order using the names of the jails, you will not need to set this value.
  If you want this jail to provide any additional values, set them here.
  This value is written upon each startup of the jail not just when it is created initially, so to have changes take effect, it's sufficient to restart it.
  **Optional**


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
