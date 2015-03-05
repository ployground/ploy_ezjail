Changelog
=========

1.2.1 - Unreleased
------------------



1.2.0 - 2015-03-05
------------------

* Use new ``Executor`` helper from ploy 1.2.0 which handles ssh agent forwarding.
  [fschulze]

* Enable "local mode" where if the ``instance`` option is empty all commands
  are executed locally.
  [fschulze]


1.1.0 - 2014-10-27
------------------

* Print status of all jails when requesting status of master.
  [fschulze]

* Check jail status before trying to connect.
  [fschulze]

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
