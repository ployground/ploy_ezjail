Changelog
=========

1.0b7 - unreleased
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
