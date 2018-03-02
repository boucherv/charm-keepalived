import os
import re
from subprocess import check_output

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

def default_route_interface():
    ''' Returns the network interface of the system's default route '''
    default_interface = None
    cmd = ['route']
    output = check_output(cmd).decode('utf8')
    for line in output.split('\n'):
        if 'default' in line:
            default_interface = line.split(' ')[-1]
            return default_interface

@when('keepalived.package.installed')
@when_not('keepalived.started')
def configure_keepalived_service():
    ''' Set up the keepalived service '''

    virtual_ip = config().get('virtual_ip')
    if virtual_ip == "":
        status_set('blocked', 'Please configure virtual ips')
        return

    network_interface = config().get('network_interface')
    if network_interface == "":
        network_interface = default_route_interface()

    context = {'is_leader': is_leader(),
               'virtual_ip': virtual_ip,
               'network_interface': network_interface,
               'router_id': config().get('router_id')
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
    ipaddr = re.split('/', config()['virtual_ip'])[0]
    website.configure(port=443, private_address=ipaddr, hostname=ipaddr)


@when('loadbalancer.available', 'keepalived.started')
def loadbalancer_available(loadbalancer):
    ''' Send the virtual IP  '''
    ipaddr = re.split('/', config()['virtual_ip'])[0]
    loadbalancer.set_address_port(ipaddr, 443)
