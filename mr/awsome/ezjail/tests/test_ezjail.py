from StringIO import StringIO
from mr.awsome.config import Config
import pytest


class DummyPlugin(object):
    def __init__(self):
        self.massagers = []

    def get_massagers(self):
        return self.massagers


def test_mounts_massager_invalid_option():
    from mr.awsome.ezjail import MountsMassager
    dummyplugin = DummyPlugin()
    plugins = dict(
        dummy=dict(
            get_massagers=dummyplugin.get_massagers))
    dummyplugin.massagers.append(MountsMassager('section', 'mounts'))
    contents = StringIO("\n".join([
        "[section:foo]",
        "mounts = 1"]))
    config = Config(contents, plugins=plugins).parse()
    with pytest.raises(ValueError) as e:
        config['section']['foo']['mounts']
    assert e.value.args == ("Mount option '1' contains no equal sign.",)


def test_mounts_massager():
    from mr.awsome.ezjail import MountsMassager
    dummyplugin = DummyPlugin()
    plugins = dict(
        dummy=dict(
            get_massagers=dummyplugin.get_massagers))
    dummyplugin.massagers.append(MountsMassager('section', 'mounts'))
    contents = StringIO("\n".join([
        "[section:foo]",
        "mounts = src=foo create=no ro=yes"]))
    config = Config(contents, plugins=plugins).parse()
    assert config['section'] == {
        'foo': {
            'mounts': (
                {
                    'src': 'foo',
                    'create': False,
                    'ro': True},)}}
