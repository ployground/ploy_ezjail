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


@pytest.fixture(params=['foo', 'bar'])
def ezjail_name(request):
    return request.param


@pytest.fixture
def ctrl(ployconf, ezjail_name):
    from ploy import Controller
    import ploy_ezjail
    lines = [
        '[ez-master:warden]',
        '[ez-instance:foo]',
        'ip = 10.0.0.1']
    if ezjail_name is not 'foo':
        lines.append('ezjail-name = %s' % ezjail_name)
    ployconf.fill(lines)
    ctrl = Controller(configpath=ployconf.directory)
    ctrl.configfile = ployconf.path
    ctrl.plugins = {'ezjail': ploy_ezjail.plugin}
    return ctrl


@pytest.fixture(autouse=True)
def _exec(monkeypatch):
    from ploy_ezjail import Master
    # always fail if _exec is called
    monkeypatch.setattr(Master, '_exec', lambda *a, **k: 0 / 0)


class MasterExec:
    def __init__(self):
        self.expect = []
        self.got = []

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


def test_get_host(ctrl, ployconf):
    lines = ployconf.content().splitlines()
    lines.extend([
        '[ez-instance:foo2]',
        'ip = lo1|10.0.0.2',
        '[ez-instance:foo3]',
        'ip = lo1|10.0.0.3,vtnet0|2a03:b0c0:3:d0::3a4d:c002',
        '[ez-instance:foo4]',
        'ip = vtnet0|2a03:b0c0:3:d0::3a4d:c002'])
    ployconf.fill(lines)
    instance = ctrl.instances['foo']
    assert instance.get_host() == '10.0.0.1'
    instance = ctrl.instances['foo2']
    assert instance.get_host() == '10.0.0.2'
    instance = ctrl.instances['foo3']
    assert instance.get_host() == '10.0.0.3'
    instance = ctrl.instances['foo4']
    assert instance.get_host() == '2a03:b0c0:3:d0::3a4d:c002'


def test_start(ctrl, ezjail_name, master_exec, caplog):
    master_exec.expect = [
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list(), ''),
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list(), ''),
        ('/usr/local/bin/ezjail-admin create -c zfs %s 10.0.0.1' % ezjail_name, 0, '', ''),
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list({'name': ezjail_name, 'ip': '10.0.0.1', 'status': 'ZS'}), ''),
        ("""sh -c 'cat - > "/usr/jails/%s/etc/startup_script"'""" % ezjail_name, 0, '', ''),
        ('chmod 0700 /usr/jails/%s/etc/startup_script' % ezjail_name, 0, '', ''),
        ("""sh -c 'cat - > "/usr/jails/%s/etc/rc.d/ploy.startup_script"'""" % ezjail_name, 0, '', ''),
        ('chmod 0700 /usr/jails/%s/etc/rc.d/ploy.startup_script' % ezjail_name, 0, '', ''),
        ("""sed -i '' -e 's/\# PROVIDE:.*$/\# PROVIDE: standard_ezjail %s /' /usr/local/etc/ezjail/%s""" % (ezjail_name, ezjail_name), 0, '', ''),
        ('/usr/local/bin/ezjail-admin start %s' % ezjail_name, 0, '', '')]
    ctrl(['./bin/ploy', 'start', 'foo'])
    assert master_exec.expect == []
    assert len(master_exec.got) == 2
    assert master_exec.got[0][0] == """sh -c 'cat - > "/usr/jails/%s/etc/startup_script"'""" % ezjail_name
    assert master_exec.got[0][1] == ''
    assert master_exec.got[1][0] == """sh -c 'cat - > "/usr/jails/%s/etc/rc.d/ploy.startup_script"'""" % ezjail_name
    assert 'PROVIDE: ploy.startup_script' in master_exec.got[1][1]
    assert caplog_messages(caplog) == [
        "Creating instance 'foo'",
        "Starting instance 'foo'"]


def test_master_status(ctrl, ezjail_name, master_exec, caplog):
    master_exec.expect = [
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list({'name': ezjail_name, 'ip': '10.0.0.1', 'status': 'ZS'}), ''),
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list({'name': ezjail_name, 'ip': '10.0.0.1', 'status': 'ZS'}), '')]
    ctrl(['./bin/ploy', 'status', 'warden'])
    assert master_exec.expect == []
    assert master_exec.got == []
    assert caplog_messages(caplog) == [
        'foo                  stopped                10.0.0.1']


def test_master_status_jail_not_created(ctrl, ezjail_name, master_exec, caplog):
    master_exec.expect = [
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list(), ''),
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list(), '')]
    ctrl(['./bin/ploy', 'status', 'warden'])
    assert master_exec.expect == []
    assert master_exec.got == []
    assert caplog_messages(caplog) == [
        'foo                  unavailable            10.0.0.1']


def test_master_status_unknown_jail(ctrl, ezjail_name, master_exec, caplog):
    master_exec.expect = [
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list({'name': 'ham', 'ip': '10.0.1.1', 'status': 'ZS'}), ''),
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list({'name': 'ham', 'ip': '10.0.1.1', 'status': 'ZS'}), '')]
    ctrl(['./bin/ploy', 'status', 'warden'])
    assert master_exec.expect == []
    assert master_exec.got == []
    assert caplog_messages(caplog) == [
        'foo                  unavailable            10.0.0.1',
        'Unknown jail found: ham                         10.0.1.1']


def test_master_status_additional_jail(ctrl, ezjail_name, master_exec, caplog, ployconf):
    lines = ployconf.content().splitlines()
    lines.extend([
        '[ez-instance:ham]',
        'ip = 10.0.0.2'])
    ployconf.fill(lines)
    master_exec.expect = [
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list({'name': ezjail_name, 'ip': '10.0.0.1', 'status': 'ZS'}), ''),
        ('/usr/local/bin/ezjail-admin list', 0, ezjail_list({'name': ezjail_name, 'ip': '10.0.0.1', 'status': 'ZS'}), '')]
    ctrl(['./bin/ploy', 'status', 'warden'])
    assert master_exec.expect == []
    assert master_exec.got == []
    assert caplog_messages(caplog) == [
        'foo                  stopped                10.0.0.1',
        'ham                  unavailable            10.0.0.2']
