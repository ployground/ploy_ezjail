from mr.awsome.common import BaseMaster
from mr.awsome.plain import Instance as PlainInstance
import logging


log = logging.getLogger('mr.awsome.openvz')


class Instance(PlainInstance):
    sectiongroupname = 'ezjail-instance'

    def get_host(self):
        return self.config.get('host', self.config['ip'])


class Master(BaseMaster):
    sectiongroupname = 'ezjail-instance'
    instance_class = Instance

    def __init__(self, *args, **kwargs):
        BaseMaster.__init__(self, *args, **kwargs)
        self.instance = PlainInstance(self, self.id, self.master_config)
        self.instance.sectiongroupname = 'ezjail-master'
        self.instances[self.id] = self.instance
        self.debug = self.master_config.get('debug-commands', False)


def get_massagers():
    from mr.awsome.config import BooleanMassager
    from mr.awsome.plain import get_massagers as plain_massagers

    massagers = []

    common = []
    for massager in plain_massagers():
        common.append((massager.__class__, massager.key))

    sectiongroupname = 'ezjail-instance'
    for klass, name in common:
        massagers.append(klass(sectiongroupname, name))
    massagers.extend([
        BooleanMassager(sectiongroupname, 'no-terminate')])

    sectiongroupname = 'ezjail-master'
    for klass, name in common:
        massagers.append(klass(sectiongroupname, name))
    massagers.extend([
        BooleanMassager(sectiongroupname, 'sudo'),
        BooleanMassager(sectiongroupname, 'debug-commands')])

    return massagers


def get_masters(main_config):
    masters = main_config.get('ezjail-master', {})
    for master, master_config in masters.iteritems():
        yield Master(main_config, master, master_config)


providerplugin = dict(
    get_massagers=get_massagers,
    get_masters=get_masters)
