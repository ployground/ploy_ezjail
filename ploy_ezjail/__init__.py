from __future__ import unicode_literals
from collections import OrderedDict
from fnmatch import fnmatch
from lazy import lazy
from ploy.common import BaseMaster, StartupScriptMixin
try:
    from ploy.common import InstanceExecutor
except ImportError:
    from ploy.common import Executor as InstanceExecutor
from ploy.common import parse_ssh_keygen
from ploy.config import BaseMassager, value_asbool
from ploy.plain import Instance as PlainInstance
from ploy.proxy import ProxyInstance
import logging
import paramiko
import re
import socket
import sys
import time


log = logging.getLogger('ploy_ezjail')


class EzjailError(Exception):
    pass


rc_startup = """#!/bin/sh
#
# BEFORE: DAEMON
# PROVIDE: ploy_startup_script
#
# ploy startup script

. /etc/rc.subr

name=ploy_startup_script
start_cmd=startup

startup() {

# Remove traces of ourself
# N.B.: Do NOT rm $0, it points to /etc/rc
##########################
  rm -f "/etc/rc.d/ploy_startup_script"

  test -e /etc/startup_script && /etc/startup_script || true
  test -e /etc/startup_script && chmod 0600 /etc/startup_script

}

run_rc_command "$1"
"""


class Instance(PlainInstance, StartupScriptMixin):
    sectiongroupname = 'ez-instance'

    _id_regexp = re.compile('^[a-zA-Z0-9_]+$')

    @property
    def _name(self):
        return self.config.get('ezjail-name', self.id)

    def validate_id(self, sid):
        if self._id_regexp.match(sid) is None:
            log.error("Invalid instance name '%s'. An ezjail instance name may only contain letters, numbers and underscores." % sid)
            sys.exit(1)
        return sid

    def get_ip(self):
        first_ip = self.config['ip']
        if ',' in first_ip:
            first_ip = first_ip.split(',')[0]
        if '|' in first_ip:
            first_ip = first_ip.split('|')[1]
        return first_ip

    def get_host(self):
        return self.config.get('host', self.get_ip())

    def get_fingerprint(self):
        status = self._status()
        if status == 'unavailable':
            log.info("Instance '%s' unavailable", self.id)
            sys.exit(1)
        if status != 'running':
            log.info("Instance state: %s", status)
            sys.exit(1)
        rc, out, err = self.master.ezjail_admin('console', name=self._name, cmd='ssh-keygen -lf /etc/ssh/ssh_host_rsa_key.pub')
        info = out.split()
        return info[1]

    def get_fingerprints(self):
        status = self._status()
        if status == 'unavailable':
            log.info("Instance '%s' unavailable", self.id)
            sys.exit(1)
        if status != 'running':
            log.info("Instance state: %s", status)
            sys.exit(1)
        result = []
        rc, out, err = self.master.ezjail_admin(
            'console', name=self._name,
            cmd='ls /etc/ssh/')
        if rc != 0:
            return result
        pub_key_names = list(
            x for x in out.decode('utf-8').splitlines()
            if fnmatch(x, 'ssh_host*_key.pub'))
        for pub_key_name in pub_key_names:
            rc, out, err = self.master.ezjail_admin(
                'console', name=self._name,
                cmd='ssh-keygen -lf /etc/ssh/%s' % pub_key_name)
            if rc != 0:
                continue
            (key,) = parse_ssh_keygen(out.decode('utf-8'))
            info = dict(
                fingerprint=key.fingerprint,
                keylen=key.keylen,
                keytype=key.keytype)
            result.append(info)
        return result

    def get_massagers(self):
        return get_instance_massagers()

    def init_ssh_key(self, user=None):
        status = self._status()
        if status == 'unavailable':
            log.error("Instance '%s' unavailable", self.uid)
            raise paramiko.SSHException()
        if status != 'running':
            log.error("Instance state for '%s': %s", self.uid, status)
            raise paramiko.SSHException()
        if 'proxyhost' not in self.config:
            self.config['proxyhost'] = self.master.id
        if 'proxycommand' not in self.config:
            mi = self.master.instance
            self.config['proxycommand'] = self.proxycommand_with_instance(mi)
        return PlainInstance.init_ssh_key(self, user=user)

    def _status(self, jails=None):
        if jails is None:
            jails = self.master.ezjail_admin('list')
        if self._name not in jails:
            return 'unavailable'
        jail = jails[self._name]
        status = jail['status']
        if len(status) != 2 or status[0] not in 'DIEBZ' or status[1] not in 'RAS':
            raise EzjailError("Invalid jail status '%s' for '%s'" % (status, self._name))
        if status[1] == 'R':
            return 'running'
        elif status[1] == 'S':
            return 'stopped'
        raise EzjailError("Don't know how to handle mounted but not running jail '%s'" % self._name)

    def status(self):
        try:
            jails = self.master.ezjail_admin('list')
        except EzjailError as e:
            log.error("Can't get status of jails: %s", e)
            return
        status = self._status(jails)
        if status == 'unavailable':
            log.info("Instance '%s' unavailable", self.id)
            return
        if status != 'running':
            log.info("Instance state: %s", status)
            return
        log.info("Instance running.")
        log.info("Instances jail id: %s" % jails[self._name]['jid'])
        if self._name != self.id:
            log.info("Instances jail name: %s" % self._name)
        log.info("Instances jail ip: %s" % jails[self._name]['ip'])

    def _get_jail_config_rc(self, name):
        name = name.lower()
        value = self.config.get('rc_%s' % name)
        if name == 'provide':
            result = ['standard_ezjail', self._name]
            if value is not None:
                result.append(value)
        elif value is None:
            return
        else:
            result = [value]
        return " ".join(result)

    def start(self, overrides=None):
        jails = self.master.ezjail_admin('list')
        status = self._status(jails)
        startup_script = None
        if status == 'unavailable':
            startup_script = self.startup_script(overrides=overrides)
            log.info("Creating instance '%s'", self.id)
            if 'ip' not in self.config:
                log.error("No IP address set for instance '%s'", self.id)
                sys.exit(1)
            try:
                self.master.ezjail_admin(
                    'create',
                    name=self._name,
                    ip=self.config['ip'],
                    flavour=self.config.get('flavour'))
            except EzjailError as e:
                for line in e.args[0].splitlines():
                    log.error(line)
                sys.exit(1)
            jails = self.master.ezjail_admin('list')
            jail = jails.get(self._name)
            startup_dest = '%s/etc/startup_script' % jail['root']
            rc, out, err = self.master._exec(
                'sh', '-c', 'cat - > "%s"' % startup_dest,
                stdin=startup_script)
            if rc != 0:
                log.error("Startup script creation failed.")
                log.error(err)
                sys.exit(1)
            rc, out, err = self.master._exec("chmod", "0700", startup_dest)
            if rc != 0:
                log.error("Startup script chmod failed.")
                log.error(err)
                sys.exit(1)
            rc_startup_dest = '%s/etc/rc.d/ploy_startup_script' % jail['root']
            rc, out, err = self.master._exec(
                'sh', '-c', 'cat - > "%s"' % rc_startup_dest,
                stdin=rc_startup)
            if rc != 0:
                log.error("Startup rc script creation failed.")
                log.error(err)
                sys.exit(1)
            rc, out, err = self.master._exec("chmod", "0700", rc_startup_dest)
            if rc != 0:
                log.error("Startup rc script chmod failed.")
                log.error(err)
                sys.exit(1)
            status = self._status(jails)
        if status != 'stopped':
            log.info("Instance state: %s", status)
            log.info("Instance already started")
            return True

        for rc_name in ('BEFORE', 'PROVIDE', 'REQUIRE'):
            rc_value = self._get_jail_config_rc(rc_name)
            if rc_value is not None:
                self.master._exec(
                    "sed", "-i", "", "-e",
                    "s/\\# %s:.*$/\\# %s: %s/" % (rc_name, rc_name, rc_value),
                    "/usr/local/etc/ezjail/%s" % self._name)

        mounts = []
        for mount in self.config.get('mounts', []):
            src = mount['src'].format(
                zfs=self.master.zfs,
                name=self._name)
            dst = mount['dst'].format(
                name=self._name)
            create_mount = mount.get('create', False)
            mounts.append(dict(src=src, dst=dst, ro=mount.get('ro', False)))
            if create_mount:
                rc, out, err = self.master._exec("mkdir", "-p", src)
                if rc != 0:
                    log.error("Couldn't create source directory '%s' for mountpoint '%s'." % src, mount['src'])
                    log.error(err)
                    sys.exit(1)
        if mounts:
            jail = jails.get(self._name)
            jail_fstab = '/etc/fstab.%s' % self._name
            jail_root = jail['root'].rstrip('/')
            log.info("Setting up mount points")
            rc, out, err = self.master._exec("head", "-n", "1", jail_fstab)
            fstab = out.decode('utf-8').splitlines()
            fstab = fstab[:1]
            fstab.append('# mount points from ploy')
            for mount in mounts:
                self.master._exec(
                    "mkdir", "-p", "%s%s" % (jail_root, mount['dst']))
                if mount['ro']:
                    mode = 'ro'
                else:
                    mode = 'rw'
                fstab.append('%s %s%s nullfs %s 0 0' % (mount['src'], jail_root, mount['dst'], mode))
            fstab.append('')
            rc, out, err = self.master._exec(
                'sh', '-c', 'cat - > "%s"' % jail_fstab,
                stdin='\n'.join(fstab))
        if startup_script:
            log.info("Starting instance '%s' with startup script, this can take a while.", self.id)
        else:
            log.info("Starting instance '%s'", self.id)
        try:
            self.master.ezjail_admin(
                'start',
                name=self._name)
        except EzjailError as e:
            for line in e.args[0].splitlines():
                log.error(line)
            sys.exit(1)

    def stop(self, overrides=None):
        status = self._status()
        if status == 'unavailable':
            log.info("Instance '%s' unavailable", self.id)
            return
        if status != 'running':
            log.info("Instance state: %s", status)
            log.info("Instance not stopped")
            return
        log.info("Stopping instance '%s'", self.id)
        self.master.ezjail_admin('stop', name=self._name)
        log.info("Instance stopped")

    def terminate(self):
        jails = self.master.ezjail_admin('list')
        status = self._status(jails)
        if self.config.get('no-terminate', False):
            log.error("Instance '%s' is configured not to be terminated.", self.id)
            return
        if status == 'unavailable':
            log.info("Instance '%s' unavailable", self.id)
            return
        if status == 'running':
            log.info("Stopping instance '%s'", self.id)
            self.master.ezjail_admin('stop', name=self._name)
        if status != 'stopped':
            log.info('Waiting for jail to stop')
            while status != 'stopped':
                jails = self.master.ezjail_admin('list')
                status = self._status(jails)
                sys.stdout.write('.')
                sys.stdout.flush()
                time.sleep(1)
            print
        log.info("Terminating instance '%s'", self.id)
        self.master.ezjail_admin('delete', name=self._name)
        log.info("Instance terminated")


class ZFS_FS(object):
    def __init__(self, zfs, name, config):
        self._name = name
        self.zfs = zfs
        self.config = config
        mp_args = (
            "zfs", "get", "-Hp", "-o", "property,value",
            "mountpoint", self['path'])
        rc, rout, rerr = self.zfs.master._exec(*mp_args)
        if rc != 0 and self.config.get('create', False):
            args = ['zfs', 'create']
            for k, v in self.config.items():
                if not k.startswith('set-'):
                    continue
                args.append("-o '%s=%s'" % (k[4:], v))
            args.append(self['path'])
            rc, out, err = self.zfs.master._exec(*args)
            if rc != 0:
                log.error(
                    "Couldn't create zfs filesystem '%s' at '%s'." % (
                        self._name, self['path']))
                log.error(err)
                sys.exit(1)
        rc, out, err = self.zfs.master._exec(*mp_args)
        if rc == 0:
            info = out.strip().split(b'\t')
            assert info[0] == b'mountpoint'
            self.mountpoint = info[1].decode('ascii')
            return
        log.error(
            "Trying to use non existing zfs filesystem '%s' at '%s'." % (
                self._name, self['path']))
        sys.exit(1)

    def __getitem__(self, key):
        value = self.config[key]
        if key == 'path':
            return value.format(zfs=self.zfs)
        return value

    def __str__(self):
        return self.mountpoint


class ZFS(object):
    def __init__(self, master):
        self.master = master
        self.config = self.master.main_config.get('ez-zfs', {})
        self._cache = {}

    def __getitem__(self, key):
        if key not in self._cache:
            self._cache[key] = ZFS_FS(self, key, self.config[key])
        return self._cache[key]


class EzjailProxyInstance(ProxyInstance):
    def status(self):
        result = None
        hasstatus = hasattr(self._proxied_instance, 'status')
        if hasstatus:
            result = self._proxied_instance.status()
        if not hasstatus or self._status() == 'running':
            try:
                jails = self.master.ezjail_admin('list')
            except EzjailError as e:
                log.error("Can't get status of jails: %s", e)
                return result
            unknown = set(jails)
            for sid in sorted(self.master.instances):
                if sid == self.id:
                    continue
                instance = self.master.instances[sid]
                unknown.discard(instance._name)
                status = instance._status(jails)
                sip = instance.config.get('ip', '')
                jip = jails.get(instance._name, {}).get('ip', 'unknown ip')
                if status == 'running' and jip != sip:
                    sip = "%s != configured %s" % (jip, sip)
                log.info("%-20s %-15s %15s" % (sid, status, sip))
            for sid in sorted(unknown):
                jip = jails[sid].get('ip', 'unknown ip')
                log.warning("Unknown jail found: %-20s %15s" % (sid, jip))
        return result


class Master(BaseMaster):
    sectiongroupname = 'ez-instance'
    instance_class = Instance
    _exec = None

    def __init__(self, *args, **kwargs):
        BaseMaster.__init__(self, *args, **kwargs)
        self.debug = self.master_config.get('debug-commands', False)
        if 'instance' not in self.master_config:
            instance = PlainInstance(self, self.id, self.master_config)
        else:
            instance = self.master_config['instance']
        if instance:
            self.instance = EzjailProxyInstance(self, self.id, self.master_config, instance)
            self.instance.sectiongroupname = 'ez-master'
            self.instances[self.id] = self.instance
        else:
            self.instance = None
        prefix_args = ()
        if self.master_config.get('sudo'):
            prefix_args = ('sudo',)
        if self._exec is None:
            self._exec = InstanceExecutor(
                instance=self.instance, prefix_args=prefix_args)

    @lazy
    def zfs(self):
        return ZFS(self)

    @lazy
    def ezjail_admin_binary(self):
        binary = self.master_config.get('ezjail-admin', '/usr/local/bin/ezjail-admin')
        return binary

    def _ezjail_admin(self, *args):
        try:
            return self._exec(self.ezjail_admin_binary, *args)
        except socket.error as e:
            raise EzjailError("Couldn't connect to instance [%s]:\n%s" % (self.instance.config_id, e))

    @lazy
    def ezjail_admin_list_headers(self):
        rc, out, err = self._ezjail_admin('list')
        if rc:
            msg = out.strip() + b'\n' + err.strip()
            raise EzjailError(msg.decode('utf-8').strip())
        lines = out.decode('utf-8').splitlines()
        if len(lines) < 2:
            raise EzjailError("ezjail-admin list output too short:\n%s" % out.strip())
        headers = []
        current = ""
        for i, c in enumerate(lines[1]):
            if c != '-' or i >= len(lines[0]):
                headers.append(current.strip())
                if i >= len(lines[0]):
                    break
                current = ""
            else:
                current = current + lines[0][i]
        if headers != ['STA', 'JID', 'IP', 'Hostname', 'Root Directory']:
            raise EzjailError("ezjail-admin list output has unknown headers:\n%s" % headers)
        return ('status', 'jid', 'ip', 'name', 'root')

    def ezjail_admin(self, command, **kwargs):
        # make sure there is no whitespace in the arguments
        for k, v in kwargs.items():
            if v is None:
                continue
            if command == 'console' and k == 'cmd':
                continue
            if len(v.split()) != 1:
                log.error("The value '%s' of kwarg '%s' contains whitespace", v, k)
                sys.exit(1)
        if command == 'console':
            return self._ezjail_admin(
                'console',
                '-e',
                kwargs['cmd'],
                kwargs['name'])
        elif command == 'create':
            args = [
                'create',
                '-c', 'zfs']
            flavour = kwargs.get('flavour')
            if flavour is not None:
                args.extend(['-f', flavour])
            args.extend([
                kwargs['name'],
                kwargs['ip']])
            rc, out, err = self._ezjail_admin(*args)
            if rc:
                msg = out.strip() + b'\n' + err.strip()
                raise EzjailError(msg.decode('utf-8').strip())
        elif command == 'delete':
            rc, out, err = self._ezjail_admin(
                'delete',
                '-fw',
                kwargs['name'])
            if rc:
                msg = out.strip() + b'\n' + err.strip()
                raise EzjailError(msg.decode('utf-8').strip())
        elif command == 'list':
            rc, out, err = self._ezjail_admin('list')
            if rc:
                msg = out.strip() + b'\n' + err.strip()
                raise EzjailError(msg.decode('utf-8').strip())
            lines = out.decode('utf-8').splitlines()
            if len(lines) < 2:
                raise EzjailError("ezjail-admin list output too short:\n%s" % out.strip())
            headers = self.ezjail_admin_list_headers
            padding = [''] * len(headers)
            jails = {}
            prev_entry = None
            for line in lines[2:]:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('N/A') or line[0].isdigit():
                    # What if prev_entry is still None?
                    # the code fail here and someone who finds that failure
                    # will provide us with a patch!
                    jails[prev_entry]['ip'] = [jails[prev_entry]['ip'], line.split()[1]]
                else:
                    entry = dict(zip(headers, line.split() + padding))
                    prev_entry = entry.pop('name')
                    jails[prev_entry] = entry
            return jails
        elif command == 'start':
            rc, out, err = self._ezjail_admin(
                'start',
                kwargs['name'])
            if rc:
                msg = out.strip() + b'\n' + err.strip()
                raise EzjailError(msg.decode('utf-8').strip())
        elif command == 'stop':
            rc, out, err = self._ezjail_admin(
                'stop',
                kwargs['name'])
            if rc:
                msg = out.strip() + b'\n' + err.strip()
                raise EzjailError(msg.decode('utf-8').strip())
        else:
            raise ValueError("Unknown command '%s'" % command)


class MountsMassager(BaseMassager):
    def __call__(self, config, sectionname):
        value = BaseMassager.__call__(self, config, sectionname)
        mounts = []
        for line in value.splitlines():
            mount_options = line.split()
            if not len(mount_options):
                continue
            options = OrderedDict()
            for mount_option in mount_options:
                if '=' not in mount_option:
                    raise ValueError("Mount option '%s' contains no equal sign." % mount_option)
                (key, value) = mount_option.split('=')
                (key, value) = (key.strip(), value.strip())
                if key == 'create':
                    value = value_asbool(value)
                    if value is None:
                        raise ValueError("Unknown value %s for option %s in %s of %s:%s." % (value, key, self.key, self.sectiongroupname, sectionname))
                if key == 'ro':
                    value = value_asbool(value)
                    if value is None:
                        raise ValueError("Unknown value %s for option %s in %s of %s:%s." % (value, key, self.key, self.sectiongroupname, sectionname))
                options[key] = value
            mounts.append(options)
        return tuple(mounts)


def get_common_massagers():
    from ploy.plain import get_massagers as plain_massagers
    return [(x.__class__, x.key) for x in plain_massagers()]


def get_instance_massagers(sectiongroupname='instance'):
    from ploy.config import BooleanMassager
    from ploy.config import StartupScriptMassager

    massagers = []

    for klass, name in get_common_massagers():
        massagers.append(klass(sectiongroupname, name))
    massagers.extend([
        MountsMassager(sectiongroupname, 'mounts'),
        BooleanMassager(sectiongroupname, 'no-terminate'),
        StartupScriptMassager(sectiongroupname, 'startup_script')])
    return massagers


def get_massagers():
    from ploy.config import BooleanMassager

    massagers = []

    sectiongroupname = 'ez-instance'
    massagers.extend(get_instance_massagers(sectiongroupname))

    sectiongroupname = 'ez-master'
    for klass, name in get_common_massagers():
        massagers.append(klass(sectiongroupname, name))
    massagers.extend([
        BooleanMassager(sectiongroupname, 'sudo'),
        BooleanMassager(sectiongroupname, 'debug-commands')])

    sectiongroupname = 'ez-zfs'
    massagers.extend([
        BooleanMassager(sectiongroupname, 'create')])

    return massagers


def get_masters(ploy):
    masters = ploy.config.get('ez-master', {})
    for master, master_config in masters.items():
        yield Master(ploy, master, master_config)


plugin = dict(
    get_massagers=get_massagers,
    get_masters=get_masters)
