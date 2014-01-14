from __future__ import absolute_import


def bootstrap(**kwargs):
    from fabric.api import env, put, run, settings, hide
    from mr.awsome.common import yesno
    import math
    import os
    import sys
    env.shell = '/bin/sh -c'
    necessary_files = [
        (
            '../roles/common/files/identity.pub',
            '/mnt/root/.ssh/authorized_keys'),
        (
            'rc.conf',
            '/mnt/etc/rc.conf'),
        (
            'sshd_config',
            '/mnt/etc/ssh/sshd_config'),
        (
            '../roles/common/files/make.conf',
            '/mnt/etc/make.conf'),
        (
            '../roles/common/files/pkg.conf',
            '/mnt/usr/local/etc/pkg.conf'),
        (
            '../roles/common/files/FreeBSD.conf',
            '/mnt/usr/local/etc/pkg/repos/FreeBSD.conf')]
    for necessary_file in necessary_files:
        if not os.path.exists(necessary_file[0]):
            print "You have to create %s first." % necessary_file[0]
            sys.exit(1)
    ssh_keys = set([
        ('ssh_host_key', '-t rsa1 -b 1024'),
        ('ssh_host_rsa_key', '-t rsa'),
        ('ssh_host_dsa_key', '-t dsa'),
        ('ssh_host_ecdsa_key', '-t ecdsa')])
    for ssh_key_info in list(ssh_keys):
        ssh_key = ssh_key_info[0]
        if os.path.exists(ssh_key):
            pub_key = '%s.pub' % ssh_key
            if not os.path.exists(pub_key):
                print "Public key '%s' for '%s' missing." % (pub_key, ssh_key)
                sys.exit(1)
    # default ssh settings for mfsbsd
    env.server.config['fingerprint'] = '02:2e:b4:dd:c3:8a:b7:7b:ba:b2:4a:f0:ab:13:f4:2d'
    env.server.config['password-fallback'] = True
    env.server.config['password'] = 'mfsroot'
    # allow overwrites from the commandline
    env.server.config.update(kwargs)
    # gather infos
    with settings(hide('output')):
        mounts = run('mount')
        sysctl_devices = run('sysctl -n kern.disks').strip().split()
        realmem = run('sysctl -n hw.realmem').strip()
        realmem = float(realmem) / 1024 / 1024
        realmem = 2 ** int(math.ceil(math.log(realmem, 2)))
        interfaces = run('ifconfig -l').strip()
    cd_device = env.server.config.get('bootstrap-cd-device', 'cd0')
    if '/dev/{dev} on /rw/cdrom'.format(dev=cd_device) not in mounts:
        run('test -e /dev/{dev} && mount_cd9660 /dev/{dev} /cdrom || true'.format(dev=cd_device))
    usb_device = env.server.config.get('bootstrap-usb-device', 'da0a')
    if '/dev/{dev} on /rw/media'.format(dev=usb_device) not in mounts:
        run('test -e /dev/{dev} && mount /dev/{dev} /media || true'.format(dev=usb_device))
    bsd_url = env.server.config.get('bootstrap-bsd-url')
    if not bsd_url:
        with settings(hide('output', 'warnings'), warn_only=True):
            result = run("find /cdrom/ /media/ -name 'base.txz' -exec dirname {} \;")
            if result.return_code == 0:
                bsd_url = result.strip()
    if not bsd_url:
        print "Found no FreeBSD system to install, please specify bootstrap-bsd-url and make sure mfsbsd is running"
        return
    install_devices = [cd_device, usb_device]
    devices = set(sysctl_devices)
    for sysctl_device in sysctl_devices:
        for install_device in install_devices:
            if install_device.startswith(sysctl_device):
                devices.remove(sysctl_device)
    devices = env.server.config.get('bootstrap-system-devices', ' '.join(devices)).split()
    print "\nFound the following disk devices on the system:\n    %s" % ' '.join(sysctl_devices)
    print "\nFound the following network interfaces, now is your chance to update your rc.conf accordingly!\n    %s" % interfaces
    if not yesno("\nContinuing will destroy the existing data on the following devices:\n    %s\n\nContinue?" % ' '.join(devices)):
        return
    zfsinstall = env.server.config.get('bootstrap-zfsinstall')
    if zfsinstall:
        put(zfsinstall, '/root/bin/myzfsinstall', mode=0755)
        zfsinstall = 'myzfsinstall'
    else:
        zfsinstall = 'zfsinstall'
    # install FreeBSD in ZFS root
    devices_args = ' '.join('-d %s' % x for x in devices)
    system_pool_name = env.server.config.get('bootstrap-system-pool-name', 'system')
    data_pool_name = env.server.config.get('bootstrap-data-pool-name', 'tank')
    swap_arg = ''
    swap_size = env.server.config.get('bootstrap-swap-size', '%iM' % (realmem * 2))
    if swap_size:
        swap_arg = '-s %s' % swap_size
    system_pool_arg = ''
    system_pool_size = env.server.config.get('bootstrap-system-pool-size', '20G')
    if system_pool_size:
        system_pool_arg = '-z %s' % system_pool_size
    run('destroygeom {devices_args} -p {system_pool_name} -p {data_pool_name}'.format(
        devices_args=devices_args,
        system_pool_name=system_pool_name,
        data_pool_name=data_pool_name))
    run('{zfsinstall} {devices_args} -p {system_pool_name} -V 28 -u {bsd_url} {swap_arg} {system_pool_arg}'.format(
        zfsinstall=zfsinstall,
        devices_args=devices_args,
        system_pool_name=system_pool_name,
        bsd_url=bsd_url,
        swap_arg=swap_arg,
        system_pool_arg=system_pool_arg))
    # create partitions for data pool, but only if the system pool doesn't use
    # the whole disk anyway
    if system_pool_arg:
        for device in devices:
            run('gpart add -t freebsd-zfs -l {data_pool_name}_{device} {device}'.format(
                data_pool_name=data_pool_name,
                device=device))
    # mount devfs inside the new system
    if 'devfs on /rw/dev' not in mounts:
        run('mount -t devfs devfs /mnt/dev')
    # setup bare essentials
    run('mkdir -p /mnt/root/.ssh && chmod 0600 /mnt/root/.ssh')
    run('cp /etc/resolv.conf /mnt/etc/resolv.conf')
    run('mkdir -p /mnt/usr/local/etc/pkg/repos')
    for necessary_file in necessary_files:
        put(*necessary_file)
    # install pkg, the tarball is also used for the ezjail flavour in bootstrap_ezjail
    run('mkdir -p /mnt/var/cache/pkg/All')
    run('fetch -o /mnt/var/cache/pkg/All/pkg.txz http://pkg.freebsd.org/freebsd:9:x86:64/latest/Latest/pkg.txz')
    run('chmod 0600 /mnt/var/cache/pkg/All/pkg.txz')
    run("tar -x -C /mnt --chroot --exclude '+*' -f /mnt/var/cache/pkg/All/pkg.txz")
    # run pkg2ng for which the shared library path needs to be updated
    run('chroot /mnt /etc/rc.d/ldconfig start')
    run('chroot /mnt pkg2ng')
    # we need to install python here, because there is no way to install it via
    # ansible playbooks
    run('chroot /mnt pkg install python27')
    # set autoboot delay
    autoboot_delay = env.server.config.get('bootstrap-autoboot-delay', '-1')
    run('echo autoboot_delay=%s >> /mnt/boot/loader.conf' % autoboot_delay)
    # ssh host keys
    for ssh_key, ssh_keygen_args in ssh_keys:
        if os.path.exists(ssh_key):
            pub_key = '%s.pub' % ssh_key
            put(ssh_key, '/mnt/etc/ssh/%s' % ssh_key, mode=0600)
            put(pub_key, '/mnt/etc/ssh/%s' % pub_key, mode=0644)
        else:
            run("ssh-keygen %s -f /mnt/etc/ssh/%s -N ''" % (ssh_keygen_args, ssh_key))
    fingerprint = run("ssh-keygen -lf /mnt/etc/ssh/ssh_host_rsa_key")
    # reboot
    with settings(hide('warnings'), warn_only=True):
        run('reboot')
    print "The SSH fingerprint of the newly bootstrapped server is:"
    print fingerprint
