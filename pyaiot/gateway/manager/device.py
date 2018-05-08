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
    def __init__(self, options):
        if options.debug:
            logger.setLevel(logging.DEBUG)

        self.db = Database()
        self.nodes = self.db.get_all_devices()
        for n in self.nodes:
            n.update({'data': {}, 'active': False})
            n['data'] = {}

        self.uids = {}
        self.unkown_uids_data = {}

    def is_registered_device(self, id):
        for n in self.nodes:
            if n['device_id'] == id:
                return n
        return None

    def device_new(self, msg):
        """Add to new device"""
        uid = msg['uid']
        if uid in self.uids:
            self.uids[uid].update({'active':True})
            return
        if uid in self.unkown_uids_data:
            return

        logger.debug('Create new device:{} in uids_unknown'.format(msg['uid']))
        self.unkown_uids_data.update({uid: {}})

    def device_out(self, msg):
        uid = msg['uid']
        if uid in self.uids:
            logger.debug('Delete device:{} in udis'.format(uid))
            self.uids[uid].update({'active':False})
            del(self.uids[uid])
        elif uid in self.unkown_uids_data[uid]:
            logger.debug('Delete device:{} in udis_unkonwn'.format(uid))
            del(self.unkown_uids_data[uid])

    def device_reset(self, msg):
        logger.debug('Delete device:{} in udis_unkonwn'.format(msg['uid']))
        uid = msg['uid']
        if uid in self.uids:
            self.uids[uid].update({'active':True})
            return

    def device_update(self, msg):
        uid = msg['uid']
        if uid in self.uids:
            self.uids[uid]['data'].update({msg['endpoint']:msg['data']})
        elif uid in self.unkown_uids_data:
            self.unkown_uids_data[uid].update({msg['endpoint']:msg['data']})
            if msg['endpoint'] == 'id':
                node = self.is_registered_device(msg['data'])
                if node:
                    node.update({'active': True})
                    node['data'].update(self.unkown_uids_data[uid])
                    del(self.unkown_uids_data[uid])
                    self.uids.update({uid: node})