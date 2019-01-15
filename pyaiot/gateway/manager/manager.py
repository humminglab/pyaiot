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

from datetime import datetime
from tornado.websocket import websocket_connect
from tornado.options import options
from pyaiot.gateway.common import GatewayBase, Node
from pyaiot.common.messaging import check_broker_data, Message

from pyaiot.gateway.manager.powernode import PowerNode
from pyaiot.gateway.manager.device import Device
from pyaiot.gateway.manager.config import Config
from pyaiot.gateway.manager.log import Log
from pyaiot.gateway.manager.sync import Sync
from pyaiot.common.update import update_config, kill_aiot_manager, update_network_manager


POWER_MONITOR_INTERVAL = 3.0

logger = logging.getLogger("pyaiot.gw.manager")

class Manager(GatewayBase):
    """Tornado based gateway application for manager

    Manager is based on GatewayBase, and it is gateway.
    But Manager also has a client role.
    It create a client connection and save it in self.websock.
    And it create power control device node.

    - gateway role (on_broker_message)
       - new: inform registered device database table
       - update: check uploaded firmware image, calculate md5sum, and request ota to actived devices
    - client role (on_client_message)
       - receive all device events, save it into self.device, save log
    """
    CONFIG = 'Config'
    PROTOCOL = 'Manager'
    MIN_POWER_LOG_INTERVAL = 10.
    SUMMARY_LOG_INTERVAL = 10.

    def __init__(self, keys, options):
        super().__init__(keys, options)

        self.options = options
        if options.debug:
            logger.setLevel(logging.DEBUG)

        self.logfile = Log()
        self.config = Config()
        self.sync = Sync(self.logfile, self.config, self.notify_sync_event)

        self.device = Device(self.config, self.logfile, options)
        self.power_node = Node(str(uuid.uuid4()))
        self.power_device = None
        self.power_data = None
        self.websock = None
        self.last_power_log_time = None

        self.low_voltage_start_time = None
        self.low_voltage_state = False

        update_network_manager(self.config.config[self.CONFIG])
        asyncio.ensure_future(self.coroutine_init())

    async def coroutine_init(self):
        """Initialize Manager in coroutine"""
        asyncio.ensure_future(self.create_client_connection(
            "ws://{}:{}/ws".format(self.options.broker_host, self.options.broker_port)))

        # wait for connection with broker
        while True:
            if self.broker and self.websock:
                break
            await asyncio.sleep(0.1)

        self.logfile.write_port_log('system', json.dumps({'event': 'start'}))

        self.power_device = PowerNode(self.config)
        await self.power_device.wait_initialized()

        # power on
        await self.power_device.set_power([1, 1, 1, 1, 1])
        await self.power_device.set_pled('G', 0)

        self.power_data = await self.power_device.read()
        self.last_power_log_time = datetime.now()
        self.new_power_report()
        logger.info('Manager application started')

        loop = asyncio.get_event_loop()
        loop.call_later(self.SUMMARY_LOG_INTERVAL, self.summary_log)
        # blocking loop
        await self.process_power_node()

    def notify_sync_event(self, connected=False, uploading=False):
        color = '0'
        blink = False

        if connected:
            color = 'G'
            if uploading:
                blink = True

        if self.power_device:
            asyncio.ensure_future(self.power_device.set_led(color, blink))

    def summary_log(self):
        log = self.power_data.copy()
        log.update(dict(
            system_fault = 0
        ))
        log.update(self.device.get_seat_state())
        self.logfile.write_sys_log('info', json.dumps(log))

        loop = asyncio.get_event_loop()
        loop.call_later(self.SUMMARY_LOG_INTERVAL, self.summary_log)

    def new_power_report(self):
        """Register power device to itself(gateway), and forward all data of power device"""
        self.add_node(self.power_node)
        for key, value in self.power_data.items():
            self.forward_data_from_node(self.power_node, key, value)
            self.logfile.write_port_log('power', json.dumps({'event': 'start', key: value}))

    async def _check_power_condition(self):
        """Check low power condition and power cut"""

        # check low voltage condition
        if self.low_voltage_state:
            if self.power_device.is_good_voltage(self.power_data['in_voltage']):
                await self.power_device.set_power_mask([0, 0, 0, 0, 0])
                await self.power_device.set_power([1, 1, 1, 1, 1])
                await self.power_device.set_pled('G', 0)
                self.low_voltage_state = False
                self.logfile.write_port_log('power', json.dumps({'event': 'normal_voltage'}))
        else:
            if self.power_device.is_lower_voltage(self.power_data['in_voltage']):
                if self.low_voltage_start_time:
                    if (datetime.now() - self.low_voltage_start_time).total_seconds() > self.power_device.low_voltage_hold_time:
                        # power off by low power
                        self.low_voltage_state = True
                        self.low_voltage_start_time = None
                        await self.power_device.set_power([0, 0, 0, 0, 0])
                        await self.power_device.set_pled('R', 1)
                        self.logfile.write_port_log('power', json.dumps({'event': 'low_voltage'}))
                if self.low_voltage_start_time is None:
                    self.low_voltage_start_time = datetime.now()
            else:
                self.low_voltage_start_time = None

    async def process_power_node(self):
        """Refresh power device state and forward data only modified"""
        while True:
            old_data = self.power_data
            self.power_data = await self.power_device.read()

            if (datetime.now() - self.last_power_log_time).total_seconds() > self.MIN_POWER_LOG_INTERVAL:
                self.last_power_log_time = datetime.now()
                enable_log = True
            else:
                enable_log = False

            for key, value in self.power_data.items():
                if value != old_data[key]:
                    self.forward_data_from_node(self.power_node, key, value)
                if enable_log:
                    self.logfile.write_port_log('power', json.dumps({'event': 'info', key: value}))

            await self._check_power_condition()

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

        if message['type'] == 'new':
            data = [dict(uid=self.power_node.uid, seat_number=0, group_number=0)]
            data += self.device.get_seat_info()
            logger.debug("Notify seat info to new client '{}'.".format(data))
            self.send_to_broker(Message.update_node(self.power_node.uid, "seat_info", data))
            self.send_to_broker(Message.update_node(self.power_node.uid, "version", self.power_device.version))
        elif message['type'] == "update" and check_broker_data(message['data']):
            data = message['data']
            # Received when a client update a node
            if data['uid'] != self.power_node.uid:
                return

            if data['endpoint'] == 'trigger_ota':
                self.broadcast_upgrade()
            elif data['endpoint'] == 'remap':
                self.remap_seat(data['payload'])
                self.send_to_broker(Message.update_node(self.power_node.uid, "reload", "reload"))
        else:
            logger.debug("Invalid data received from broker '{}'."
                         .format(message['data']))

    def remap_seat(self, payload):
        group_table = ['', 'A', 'B', 'C', 'D']
        ini = '[Seats]\n'
        for i in range(1, self.config['total_seats']+1):
            if str(i) in payload:
                node = payload[str(i)]
                ini += '%d = %s,%s\n' % (i, node['uid'], group_table[node['group_number']])
            else:
                ini += '%d = \n' % i

        update_config(ini)
        kill_aiot_manager()

    def md5(self, firmware_filename):
        """Calculate md5 sum of firmware"""
        hash_md5 = hashlib.md5()
        with open(firmware_filename, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def broadcast_upgrade(self):
        """Broadcast update notification to all active devices"""
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
