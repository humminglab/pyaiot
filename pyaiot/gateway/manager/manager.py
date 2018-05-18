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

"""Manager module to coordinate total system"""

import logging
import uuid
import asyncio
import json
import os
import glob
import hashlib

from tornado.websocket import websocket_connect
from tornado.options import options
from pyaiot.gateway.common import GatewayBase, Node
from pyaiot.common.messaging import check_broker_data, Message

try:
    from .powernode import PowerNode
    from .device import Device
except:
    from powernode import PowerNode
    from device import Device


POWER_MONITOR_INTERVAL = 3.0

logger = logging.getLogger("pyaiot.gw.manager")

class Manager(GatewayBase):
    """Tornado based gateway application for manager"""

    PROTOCOL = 'Manager'

    def __init__(self, keys, options):
        super().__init__(keys, options)

        self.options = options
        if options.debug:
            logger.setLevel(logging.DEBUG)

        self.device = Device(options)
        self.power_node = Node(str(uuid.uuid4()))
        self.power_device = None
        self.power_data = None
        self.websock = None
        self.client_uid = None
        asyncio.ensure_future(self.coroutine_init())

    async def coroutine_init(self):
        asyncio.ensure_future(self.create_client_connection(
            "ws://{}:{}/ws".format(self.options.broker_host, self.options.broker_port)))

        # wait for connection with broker
        while True:
            if self.broker and self.websock:
                break
            await asyncio.sleep(0.1)

        self.power_device = PowerNode()
        await self.power_device.wait_initialized()

        # power on
        await self.power_device.set([1, 1, 1, 1, 1])

        self.power_data = await self.power_device.read()
        self.new_power_report()
        logger.info('Manager application started')
        await self.process_power_node()

    def new_power_report(self):
        self.add_node(self.power_node)
        for key, value in self.power_data.items():
            self.forward_data_from_node(self.power_node, key, value)

    async def process_power_node(self):
        while True:
            old_data = self.power_data
            self.power_data = await self.power_device.read()
            for key, value in self.power_data.items():
                if value != old_data[key]:
                    self.forward_data_from_node(self.power_node, key, value)
            await asyncio.sleep(POWER_MONITOR_INTERVAL)

    def on_client_message(self, message):
        """Handle a message received from gateways to client."""
        logger.debug("Handling message '{}' received from gateway."
                     .format(message))
        message = json.loads(message)

        # skip power node
        if message['uid'] == self.power_node.uid:
            return

        if message['type'] == 'new':
            self.device.device_new(message)
        elif message['type'] == 'out':
            self.device.device_out(message)
        elif message['type'] == 'reset':
            self.device.device_reset(message)
        elif message['type'] == 'update':
            self.device.device_update(message)
        else:
            logger.debug("Invalid data received from broker '{}'."
                         .format(message['data']))

    def on_broker_message(self, message):
        """Handle a message received from client to gateways"""
        super(Manager, self).on_broker_message(message)
        message = json.loads(message)

        # get uid of itself
        if not self.client_uid and message['type'] == 'new' and message['data'] == 'manager_client':
            self.client_uid = message['src']
            return

        # from itself
        if message['src'] == self.client_uid:
            return

        if message['type'] == 'new':
            data = self.device.get_seat_info()
            data[0] = dict(uid=self.power_node.uid, seat_number=0, group_number=0)
            logger.debug("Notify seat info to new client '{}'.".format(data))
            self.send_to_broker(Message.update_node(self.power_node.uid, "seat_info", data))
        elif (message['type'] == "update" and
              check_broker_data(message['data'])):
            data = message['data']
            # Received when a client update a node
            if data['uid'] != self.power_node.uid:
                return

            if data['endpoint'] == 'trigger_ota':
                self.broadcast_upgrade()
        else:
            logger.debug("Invalid data received from broker '{}'."
                         .format(message['data']))

    def md5(self, firmware_filename):
        hash_md5 = hashlib.md5()
        with open(firmware_filename, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def broadcast_upgrade(self):
        fullnames = [f for f in glob.glob('{}firmware/node-*.img'.format(options.static_path))]
        if len(fullnames) <= 0:
            logger.error("Can not find firmware file")
            return

        fullname = fullnames[0]
        filename = os.path.basename(fullname)
        name, ext = os.path.splitext(filename)
        _, version = name.split('-')

        if not name and not ext and not version:
            return

        path = '/static/firmware/{}'.format(filename)
        md5 = self.md5(fullname)
        nodes = self.device.get_upgradable_devices(version)
        logger.debug('Firmwware {}, MD5={}'.format(filename, md5))

        for node in nodes:
            self.websock.write_message(json.dumps({
                'type': 'update',
                'data': {
                    'uid': node['device_id'],
                    'endpoint': 'version',
                    'payload': json.dumps({
                        # FIXME: Need to get web server address dynamically
                        'hostname': "192.168.0.2",
                        'port': options.web_port,
                        'md5': md5,
                        'path': path
                    })
                }
            }));

    async def create_client_connection(self, url):
        """Create an asynchronous connection to the broker."""
        while True:
            try:
                self.websock = await websocket_connect(url)
            except ConnectionRefusedError:
                logger.warning("Cannot connect, retrying in 3s")
            else:
                logger.info("Connected to websock client")
                self.websock.write_message(json.dumps({'type':'new', 'data':'manager_client'}))
                while True:
                    message = await self.websock.read_message()
                    if message is None:
                        logger.warning("Connection with broker lost.")
                        break
                    self.on_client_message(message)

            await asyncio.sleep(3)

    def discover_node(self, node):
        logger.debug("discover_node '{}'".format(node))

    def update_node_resource(self, node, endpoint, payload):
        logger.debug("update_node_resource '{}'".format(node))
