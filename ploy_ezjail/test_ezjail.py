try:
    from StringIO import StringIO
except ImportError:  # pragma: nocover
    from io import StringIO
from hashlib import md5
from ploy.common import shjoin
from ploy.config import Config
import logging
import pytest


log = logging.getLogger('ploy_ezjail_tests')


class DummyPlugin(object):
    def __init__(self):
        self.massagers = []

    def get_massagers(self):
        return self.massagers


def test_mounts_massager_invalid_option():
    from ploy_ezjail import MountsMassager
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
    from ploy_ezjail import MountsMassager
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


@pytest.yield_fixture
def ctrl(ployconf):
    from ploy import Controller
    import ploy_ezjail
    ployconf.fill([
        '[ez-master:warden]',
        '[ez-instance:foo]',
        'ip = 10.0.0.1'])
    ctrl = Controller(configpath=ployconf.directory)
    ctrl.plugins = {'ezjail': ploy_ezjail.plugin}
    yield ctrl


@pytest.fixture(autouse=True)
def _exec(monkeypatch):
    from ploy_ezjail import Master
    # always fail if _exec is called
    monkeypatch.setattr(Master, '_exec', lambda *a, **k: 0 / 0)


class MasterExec:
    expect = []
    got = []

    def __call__(self, *cmd_args, **kw):
        stdin = kw.get('stdin')
        cmd = shjoin(cmd_args)
        log.debug('ezjail %r stdin=%r', cmd, stdin)
        try:
            expected = self.expect.pop(0)
        except IndexError:  # pragma: no cover - only on failures
            expected = ('', 0, '', '')
        cmd_args, rc, out, err = expected
        assert cmd == cmd_args
        if stdin is not None:
            self.got.append((cmd, stdin))
        return (rc, out, err)


@pytest.fixture
def master_exec(monkeypatch):
    from ploy_ezjail import Master
    me = MasterExec()
    monkeypatch.setattr(Master, '_exec', me)
    return me


def ezjail_list(*jails):
    lines = [
        'STA JID  IP              Hostname                       Root Directory',
        '--- ---- --------------- ------------------------------ ------------------------']
    for jail in jails:
        name = jail['name']
        fake_id = md5(name.encode('ascii')).digest()[0]
        if isinstance(fake_id, int):  # pragma: nocover
            fake_id = (fake_id % 100) + 1
        else:  # pragma: nocover
            fake_id = (ord(fake_id) % 100) + 1
        status = "%s   " % jail['status']
        jid = "%d    " % jail.get('jid', fake_id)
        ip = "%s               " % jail.get('ip', "10.0.0.%d" % fake_id)
        hostname = "%s                              " % name
        root = "/usr/jails/%s" % name
        lines.append('%s %s %s %s %s' % (
            status[:3], jid[:4], ip[:15], hostname[:30], root))
    return '\n'.join(lines)


def caplog_messages(caplog, level=logging.INFO):
    return [
        x.message
        for x in caplog.records()
        if x.levelno >= level]


def test_start(ctrl, master_exec, caplog):
    master_exec.expect = [
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list(), ''),
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list(), ''),
        ('/usr/local/bin/ezjail-admin create -c zfs foo 10.0.0.1', 0, '', ''),
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list({'name': 'foo', 'ip': '10.0.0.1', 'status': 'ZS'}), ''),
        ("""sh -c 'cat - > "/usr/jails/foo/etc/startup_script"'""", 0, '', ''),
        ('chmod 0700 /usr/jails/foo/etc/startup_script', 0, '', ''),
        ("""sh -c 'cat - > "/usr/jails/foo/etc/rc.d/ploy.startup_script"'""", 0, '', ''),
        ('chmod 0700 /usr/jails/foo/etc/rc.d/ploy.startup_script', 0, '', ''),
        ("""sed -i '' -e 's/\# PROVIDE:.*$/\# PROVIDE: standard_ezjail foo /' /usr/local/etc/ezjail/foo""", 0, '', ''),
        ('/usr/local/bin/ezjail-admin start foo', 0, '', '')]
    ctrl(['./bin/ploy', 'start', 'foo'])
    assert master_exec.expect == []
    assert len(master_exec.got) == 2
    assert master_exec.got[0][0] == """sh -c 'cat - > "/usr/jails/foo/etc/startup_script"'"""
    assert master_exec.got[0][1] == ''
    assert master_exec.got[1][0] == """sh -c 'cat - > "/usr/jails/foo/etc/rc.d/ploy.startup_script"'"""
    assert 'PROVIDE: ploy.startup_script' in master_exec.got[1][1]
    assert caplog_messages(caplog) == [
        "Creating instance 'foo'",
        "Starting instance 'foo'"]
