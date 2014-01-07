from lazy import lazy
from mr.awsome.common import BaseMaster
from mr.awsome.plain import Instance as PlainInstance
import logging
import sys
import time


log = logging.getLogger('mr.awsome.ezjail')


class EzjailError(Exception):
    pass


class Instance(PlainInstance):
    sectiongroupname = 'ez-instance'

    def get_host(self):
        return self.config.get('host', self.config['ip'])

    def get_fingerprint(self):
        status = self._status()
        if status == 'unavailable':
            log.info("Instance '%s' unavailable", self.id)
            sys.exit(1)
        if status != 'running':
            log.info("Instance state: %s", status)
            sys.exit(1)
        rc, out, err = self.master.ezjail_admin('console', name=self.id, cmd='ssh-keygen -lf /etc/ssh/ssh_host_rsa_key.pub')
        self.master.conn.close()
        info = out.split()
        return info[1]

    def _status(self, jails=None):
        if jails is None:
            jails = self.master.ezjail_admin('list')
        if self.id not in jails:
            return 'unavailable'
        jail = jails[self.id]
        status = jail['status']
        if len(status) != 2 or status[0] not in 'DIEBZ' or status[1] not in 'RAS':
            raise EzjailError("Invalid jail status '%s' for '%s'" % (status, self.id))
        if status[1] == 'R':
            return 'running'
        elif status[1] == 'S':
            return 'stopped'
        raise EzjailError("Don't know how to handle mounted but not running jail '%s'" % self.id)

    def status(self):
        status = self._status()
        if status == 'unavailable':
            log.info("Instance '%s' unavailable", self.id)
            return
        if status != 'running':
            log.info("Instance state: %s", status)
            return
        log.info("Instance running.")

    def start(self, overrides=None):
        status = self._status()
        create = False
        if status == 'unavailable':
            create = True
            log.info("Creating instance '%s'", self.id)
            if 'ip' not in self.config:
                log.error("No IP address set for instance '%s'", self.id)
                sys.exit(1)
            try:
                self.master.ezjail_admin(
                    'create',
                    name=self.id,
                    ip=self.config['ip'],
                    flavour=self.config.get('flavour'))
            except EzjailError as e:
                for line in e.args[0].split('\n'):
                    log.error(line)
                sys.exit(1)
            status = self._status()
        if status != 'stopped':
            log.info("Instance state: %s", status)
            log.info("Instance already started")
            return True
        log.info("Starting instance '%s'", self.id)
        try:
            self.master.ezjail_admin(
                'start',
                name=self.id)
        except EzjailError as e:
            for line in e.args[0].split('\n'):
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
        self.master.ezjail_admin('stop', name=self.id)
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
            self.master.ezjail_admin('stop', name=self.id)
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
        self.master.ezjail_admin('delete', name=self.id)
        log.info("Instance terminated")


class Master(BaseMaster):
    sectiongroupname = 'ez-instance'
    instance_class = Instance

    def __init__(self, *args, **kwargs):
        BaseMaster.__init__(self, *args, **kwargs)
        self.instance = PlainInstance(self, self.id, self.master_config)
        self.instance.sectiongroupname = 'ez-master'
        self.instances[self.id] = self.instance
        self.debug = self.master_config.get('debug-commands', False)

    @lazy
    def binary_prefix(self):
        if self.master_config.get('sudo'):
            return "sudo "
        return ""

    @lazy
    def ezjail_admin_binary(self):
        binary = self.binary_prefix + self.master_config.get('ezjail-admin', '/usr/local/bin/ezjail-admin')
        return binary

    @lazy
    def conn(self):
        try:
            from paramiko import SSHException
            SSHException  # shutup pyflakes
        except ImportError:
            from ssh import SSHException
        try:
            ssh_info = self.instance.init_ssh_key()
        except SSHException, e:
            log.error("Couldn't connect to vz-master:%s." % self.id)
            log.error(unicode(e))
            sys.exit(1)
        return ssh_info['client']

    def _exec(self, cmd, debug=False, stdin=None):
        if debug:
            log.info(cmd)
        chan = self.conn.get_transport().open_session()
        if stdin is not None:
            rin = chan.makefile('wb', -1)
        rout = chan.makefile('rb', -1)
        rerr = chan.makefile_stderr('rb', -1)
        chan.exec_command(cmd)
        if stdin is not None:
            rin.write(stdin)
            rin.flush()
            chan.shutdown_write()
        out = rout.read()
        err = rerr.read()
        rc = chan.recv_exit_status()
        if debug and out.strip():
            log.info(out)
        if debug and err.strip():
            log.error(err)
        return rc, out, err

    def _ezjail_admin(self, *args):
        return self._exec(
            "%s %s" % (self.ezjail_admin_binary, " ".join(args)),
            self.debug)

    @lazy
    def ezjail_admin_list_headers(self):
        rc, out, err = self._ezjail_admin('list')
        if rc:
            raise EzjailError(err.strip())
        lines = out.split('\n')
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
                kwargs[k] = v.replace('"', '\\"')
                continue
            if len(v.split()) != 1:
                log.error("The value '%s' of kwarg '%s' contains whitespace", v, k)
                sys.exit(1)
        if command == 'console':
            return self._ezjail_admin(
                'console',
                '-e',
                '"%s"' % kwargs['cmd'],
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
                raise EzjailError(err.strip())
        elif command == 'delete':
            rc, out, err = self._ezjail_admin(
                'delete',
                '-w',
                kwargs['name'])
            if rc:
                raise EzjailError(err.strip())
        elif command == 'list':
            rc, out, err = self._ezjail_admin('list')
            if rc:
                raise EzjailError(err.strip())
            lines = out.split('\n')
            if len(lines) < 2:
                raise EzjailError("ezjail-admin list output too short:\n%s" % out.strip())
            headers = self.ezjail_admin_list_headers
            jails = {}
            for line in lines[2:]:
                line = line.strip()
                if not line:
                    continue
                entry = dict(zip(headers, line.split()))
                jails[entry.pop('name')] = entry
            return jails
        elif command == 'start':
            rc, out, err = self._ezjail_admin(
                'start',
                kwargs['name'])
            if rc:
                raise EzjailError(err.strip())
        elif command == 'stop':
            rc, out, err = self._ezjail_admin(
                'stop',
                kwargs['name'])
            if rc:
                raise EzjailError(err.strip())
        else:
            raise ValueError("Unknown command '%s'" % command)


def get_massagers():
    from mr.awsome.config import BooleanMassager
    from mr.awsome.plain import get_massagers as plain_massagers

    massagers = []

    common = []
    for massager in plain_massagers():
        common.append((massager.__class__, massager.key))

    sectiongroupname = 'ez-instance'
    for klass, name in common:
        massagers.append(klass(sectiongroupname, name))
    massagers.extend([
        BooleanMassager(sectiongroupname, 'no-terminate')])

    sectiongroupname = 'ez-master'
    for klass, name in common:
        massagers.append(klass(sectiongroupname, name))
    massagers.extend([
        BooleanMassager(sectiongroupname, 'sudo'),
        BooleanMassager(sectiongroupname, 'debug-commands')])

    return massagers


def get_masters(main_config):
    masters = main_config.get('ez-master', {})
    for master, master_config in masters.iteritems():
        yield Master(main_config, master, master_config)


providerplugin = dict(
    get_massagers=get_massagers,
    get_masters=get_masters)
