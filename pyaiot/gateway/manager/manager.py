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
import time
import uuid
import asyncio
import json

from tornado import gen
from tornado.websocket import websocket_connect
from tornado.ioloop import PeriodicCallback

from pyaiot.common.messaging import Message as Msg
from pyaiot.gateway.common import GatewayBase, Node

if __name__ == '__main__':
    from device import Device
else:
    from .device import Device


logger = logging.getLogger("pyaiot.gw.manager")

class Manager(GatewayBase):
    """Tornado based gateway application for manager"""

    PROTOCOL = 'Manager'

    def __init__(self, keys, options):
        if options.debug:
            logger.setLevel(logging.DEBUG)

        self.device = Device(options)
        self.websock = None

        super().__init__(keys, options)

        self.create_client_connection(
            "ws://{}:{}/ws".format(options.broker_host, options.broker_port))

        logger.info('Manager application started')

    def on_client_message(self, message):
        """Handle a message received from gateways."""
        logger.debug("Handling message '{}' received from broker."
                     .format(message))
        message = json.loads(message)

        if message['type'] == 'new':
            self.device.device_new(message)
        elif message['type'] == 'out':
            self.device.device_out(message)
        elif message['type'] == 'reset':
            self.devcie.device_reset(message)
        elif message['type'] == 'update':
            self.device.device_update(message)
        else:
            logger.debug("Invalid data received from broker '{}'."
                         .format(message['data']))

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

    async def discover_node(self, node):
        logger.debug("discover_node '{}'".format(node))

    async def update_node_resource(self, node, endpoint, payload):
        logger.debug("update_node_resource '{}'".format(node))
