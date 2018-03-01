import os
import re

from charms.reactive import set_state, when, when_not
from charms.reactive.flags import remove_state
from charms.templating.jinja2 import render


from charmhelpers.fetch import apt_update, apt_install
from charmhelpers.core.hookenv import log, status_set
from charmhelpers.core.hookenv import config, is_leader
from charmhelpers.core.host import service_restart


SYSCTL_FILE = os.path.join(os.sep, 'etc', 'sysctl.d', '50-keepalived.conf')
KEEPALIVED_CONFIG_FILE = os.path.join(os.sep, 'etc', 'keepalived',
                                      'keepalived.conf')


@when_not('keepalived.package.installed')
def install_keepalived_package():
    ''' Install keepalived package '''
    status_set('maintenance', 'Installing keepalived')

    apt_update(fatal=True)
    apt_install('keepalived', fatal=True)

    set_state('keepalived.package.installed')


@when('keepalived.package.installed')
@when_not('keepalived.started')
def configure_keepalived_service():
    ''' Set up the keepalived service '''

    virtual_ip = config().get('virtual-ip')
    if virtual_ip == "":
        status_set('blocked', 'Please configure virtual ips')
        return

    context = {'is_leader': is_leader(),
               'virtual-ip': virtual_ip,
               'network-interface': config().get('network-interface'),
               'router-id': config().get('router-id')
              }
    render(source='keepalived.conf',
           target=KEEPALIVED_CONFIG_FILE,
           context=context,
           perms=0o644)
    service_restart('keepalived')

    render(source='50-keepalived.conf',
           target=SYSCTL_FILE,
           context={'sysctl': {'net.ipv4.ip_nonlocal_bind': 1}},
           perms=0o644)
    service_restart('procps')

    status_set('active', 'VIP ready')
    set_state('keepalived.started')


@when('config.changed')
def reconfigure():
    remove_state('keepalived.started')


@when('website.available', 'keepalived.started')
def website_available(website):
    ''' Send the port '''
    ipaddr = re.split('/', config()['virtual-ip'])[0]
    website.configure(port=443, private_address=ipaddr, hostname=ipaddr)


@when('loadbalancer.available', 'keepalived.started')
def loadbalancer_available(loadbalancer):
    ''' Send the virtual IP  '''
    ipaddr = re.split('/', config()['virtual-ip'])[0]
    loadbalancer.set_address_port(ipaddr, 443)
