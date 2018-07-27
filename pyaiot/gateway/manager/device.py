# Copyright 2018 HummingLab
# Contributor(s) : yslee@humminglab.io
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import logging
import json

logger = logging.getLogger("pyaiot.gw.device")

try:
    from .config import Config
except:
    from config import Config


type_table = dict(
    current=int,
    fail=int,
    fastcharge=int,
    interval=int,
    usb=int,
    voltage=int
)

class Device():
    def __init__(self, config, logfile, options):
        if options.debug:
            logger.setLevel(logging.DEBUG)

        self.config = config
        self.logfile = logfile
        self.total_seats = self.config.get_total_seat()
        self.nodes = self.config.get_all_devices()
        for n in self.nodes:
            n.update({'data': {}, 'active': False})
            n['data'] = {}

        self.uids = {node['device_id']: node for node in self.nodes}
        self.unkown_uids_data = {}

    def get_seat_info(self):
        # seat number start from 1
        data = [None] * (self.total_seats)
        for node in self.nodes:
            data[node['seat_number'] - 1] = dict(
                uid=node['device_id'],
                seat_number=node['seat_number'],
                group_number=node['group_number'])
        return data

    def get_seat_state(self):
        state = dict(
            port_fault=[1] * self.total_seats,
            port_charging=[0] * self.total_seats,
            port_fast_charge=[0] * self.total_seats
        )

        for node in self.nodes:
            index = node['seat_number'] - 1
            if node['active']:
                if 'fail' in node['data'] and node['data']['fail']:
                    state['port_fault'][index] = node['data']['fail']
                else:
                    state['port_fault'][index] = 0

                if 'usb' in node['data'] and node['data']['usb']:
                    state['port_charging'][index] = 1

                if 'fastcharge' in node['data'] and node['data']['fastcharge']:
                    state['port_fast_charge'][index] = 1
        return state

    def get_activate_devices(self):
        """get registered and activated devices"""
        nodes = [node for node in self.nodes if node['active']]
        return nodes

    def get_upgradable_devices(self, target_version):
        """get devices to need to upgrade"""
        nodes = [node for node in self.nodes if node['active'] and 'version' in node['data']
                 and node['data']['version'] != target_version]
        return nodes

    def is_registered_device(self, id):
        return self.uids[id] if id in self.uids else None

    def device_new(self, msg):
        """Add to new device"""
        uid = msg['uid']
        data = {'active':True}
        if uid in self.uids:
            self.uids[uid].update(data)
            self.logfile.write_port_log(uid, json.dumps({'event': 'start', 'seat': self.uids[uid]['seat_number']}))
            return
        if uid in self.unkown_uids_data:
            self.unkown_uids_data[uid].update(data)
            return

        logger.debug('Create new device:{} in uids_unknown'.format(msg['uid']))
        self.logfile.write_port_log(uid, json.dumps({'event': 'start', 'seat': 'unknown'}))
        self.unkown_uids_data.update({uid: data})

    def device_out(self, msg):
        uid = msg['uid']
        if uid in self.uids:
            logger.debug('Delete device:{} in udis'.format(uid))
            self.uids[uid].update({'active':False})
            self.logfile.write_port_log(uid, json.dumps({'event': 'start', 'seat': self.uids[uid]['seat_number']}))
        elif uid in self.unkown_uids_data[uid]:
            logger.debug('Delete device:{} in udis_unkonwn'.format(uid))
            del(self.unkown_uids_data[uid])
            self.logfile.write_port_log(uid, json.dumps({'event': 'stop', 'seat': 'unknown'}))

    def device_reset(self, msg):
        logger.debug('Delete device:{} in udis_unkonwn'.format(msg['uid']))
        uid = msg['uid']
        if uid in self.uids:
            self.uids[uid].update({'active':True})
            self.logfile.write_port_log(uid, json.dumps({'event': 'reset', 'seat': self.uids[uid]['seat_number']}))
            return

    def device_update(self, msg):
        uid = msg['uid']
        value = type_table[msg['endpoint']](msg['data']) if msg['endpoint'] in type_table else msg['data']
        if uid in self.uids:
            self.uids[uid]['data'].update({msg['endpoint']:value})
            self.logfile.write_port_log(uid, json.dumps({'event': 'info', 'seat': self.uids[uid]['seat_number'], msg['endpoint']: value}))
        elif uid in self.unkown_uids_data:
            self.unkown_uids_data[uid].update({msg['endpoint']:value})
