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

logger = logging.getLogger("pyaiot.gw.device")

try:
    from .database import Database
except:
    from database import Database

class Device():
    def __init__(self, database, options):
        if options.debug:
            logger.setLevel(logging.DEBUG)

        self.db = database
        self.total_seats = int(self.db.get_conf('total_seats', 24))
        self.nodes = self.db.get_all_devices()
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

    # def get_seat_state(self):
    #     state = dict(
    #         port_fault = [0] * (self.total_seats + 1),
    #         port_charging = [0] * (self.total_seats + 1),
    #         port_fast_charge = []
    #     )
    #
    #     for node in self.nodes:
    #         if
    #

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
            self.db.insert_port_log('info', 'new seat {}'.format(self.uids[uid]['seat_number']), uid)
            return
        if uid in self.unkown_uids_data:
            self.unkown_uids_data[uid].update(data)
            return

        logger.debug('Create new device:{} in uids_unknown'.format(msg['uid']))
        self.db.insert_port_log('info', 'new unknown device {}'.format(uid), 'other')
        self.unkown_uids_data.update({uid: data})

    def device_out(self, msg):
        uid = msg['uid']
        if uid in self.uids:
            logger.debug('Delete device:{} in udis'.format(uid))
            self.uids[uid].update({'active':False})
            self.db.insert_port_log('info', 'out seat {}'.format(self.uids[uid]['seat_number']), uid)
        elif uid in self.unkown_uids_data[uid]:
            logger.debug('Delete device:{} in udis_unkonwn'.format(uid))
            del(self.unkown_uids_data[uid])
            self.db.insert_port_log('info', 'out unknown device {}'.format(uid), 'other')

    def device_reset(self, msg):
        logger.debug('Delete device:{} in udis_unkonwn'.format(msg['uid']))
        uid = msg['uid']
        if uid in self.uids:
            self.uids[uid].update({'active':True})
            self.db.insert_port_log('info', 'reset seat {}'.format(self.uids[uid]['seat_number']), uid)
            return

    def device_update(self, msg):
        uid = msg['uid']
        if uid in self.uids:
            self.uids[uid]['data'].update({msg['endpoint']:msg['data']})
            self.db.insert_port_log(msg['endpoint'], msg['data'], uid)
        elif uid in self.unkown_uids_data:
            self.unkown_uids_data[uid].update({msg['endpoint']:msg['data']})
