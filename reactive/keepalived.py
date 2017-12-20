import os
import re

from charms.reactive import set_state, when, when_not, hook

from charmhelpers.fetch import apt_update, apt_install
from charmhelpers.core.hookenv import log, status_set, relation_set
from charmhelpers.core.hookenv import config, relation_id, is_leader
from charmhelpers.core.host import service_stop, service_restart
from charmhelpers.core.services import helpers
from charmhelpers.core.services.base import ServiceManager

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
def configure_keepalived_service():
    ''' Set up the keepalived service '''
    manager = ServiceManager([
        {
            'service': 'keepalived',
            'required_data': [
                helpers.RequiredConfig('virtual-ip',
                                       'network-interface',
                                       'router-id'),
                {'is_leader': is_leader()}
            ],
            'data_ready': [
                lambda arg: status_set('active', 'VIP ready'),
                helpers.template(
                    source='keepalived.conf',
                    target=KEEPALIVED_CONFIG_FILE,
                    perms=0o644
                )
            ],
            # keepalived has no "status" commandjuju charm UnicodeDecodeError:
            'stop': [
                lambda arg: service_stop('keepalived')
            ],
            'start': [
                lambda arg: service_restart('keepalived')
            ],
        },
        {
            'service': 'procps',
            'required_data': [
                {'sysctl': {'net.ipv4.ip_nonlocal_bind': 1}},
            ],
            'data_ready': [
                helpers.template(
                    source='50-keepalived.conf',
                    target=SYSCTL_FILE,
                    perms=0o644
                )
            ],
        }
    ])
    manager.manage()




@hook('website-relation-joined')
def website_relation_joined():
    ''' Send the virtual IP '''
    ipaddr = re.split('/', config()['virtual-ip'])[0]

    relation_settings = {
        "hostname": ipaddr,
        "port": 443
    }

    relation_set(relation_id=relation_id(), relation_settings=relation_settings)

@hook('loadbalancer-relation-joined')
def loadbalancer_relation_joined():
    ''' Send the virtual IP  '''
    ipaddr = re.split('/', config()['virtual-ip'])[0]

    relation_settings = {
        "public-address": ipaddr,
        "port": 443
    }

    relation_set(relation_id=relation_id(), relation_settings=relation_settings)
