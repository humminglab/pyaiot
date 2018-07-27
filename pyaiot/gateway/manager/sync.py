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

"""Sync with server"""

import datetime
import json
import asyncio
import logging
import netifaces
from pyroute2 import IPRoute
from threading import Thread

logger = logging.getLogger("pyaiot.manager.sync")
logger.setLevel(logging.DEBUG)

WLAN = 'wlan0'


def pyroute_monitor(loop, sync):
    with IPRoute() as ipr:
        ipr.bind()

        while True:
            msgs = ipr.get()
            for msg in msgs:
                if msg['event'] == 'RTM_NEWADDR' and msg.get_attr('IFA_LABEL') == WLAN:
                    logger.info('WiFi Connected: {}'.format(msg.get_attr('IFA_ADDRESS')))
                    loop.call_soon_threadsafe(sync.on_wlan_event(), True, msg.get_attr('IFA_ADDRESS'))
                elif msg['event'] == 'RTM_DELADDR' and msg.get_attr('IFA_LABEL') == WLAN:
                    logger.info('WiFi Disconnected')
                    loop.call_soon_threadsafe(sync.on_wlan_event(), False)


class Sync():
    def __init__(self, logfile):
        self.logfile = logfile
        self.last_update_time = datetime.datetime(1900, 1, 1)
        loop = asyncio.get_event_loop()

        self.thread = Thread(target=pyroute_monitor, args=(loop, self))
        self.thread.start()

        self.trigger_upload()


    def on_wlan_event(self, up, ip = None):
        logs = dict(up=up)
        if ip:
            logs['ip'] = ip
        self.logfile.write_port_log('wlan', json.dumps(logs))

        if up:
            self.trigger_upload()

    def trigger_upload(self):
        addrs = netifaces.ifaddresses(WLAN)
        if not netifaces.AF_INET in addrs:
            logger.info('Upload cancel: WiFi Disconnected')
            return

        # check old files
        now = datetime.datetime.now()

