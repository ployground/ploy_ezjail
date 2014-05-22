Changelog
=========

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
