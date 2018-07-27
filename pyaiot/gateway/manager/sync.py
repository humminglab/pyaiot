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

import os
import datetime
import json
import asyncio
import logging
import netifaces
from tornado.httpclient import HTTPRequest, AsyncHTTPClient
from pyroute2 import IPRoute
from threading import Thread

try:
    from .config import DEFAULT_CONFIG_FILENAME
except:
    from config import DEFAULT_CONFIG_FILENAME

logger = logging.getLogger("pyaiot.manager.sync")
logger.setLevel(logging.DEBUG)

WLAN = 'wlan0'
MIN_REPORT_INTERVAL_SECS = (10 * 60)


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
    def __init__(self, logfile, config):
        self.logfile = logfile
        self.config = config
        self.last_update_time = datetime.datetime(1900, 1, 1)
        loop = asyncio.get_event_loop()
        self.handle = loop.call_soon(self.trigger_upload)

        self.thread = Thread(target=pyroute_monitor, args=(loop, self))
        self.thread.start()

    def on_wlan_event(self, up, ip = None):
        logs = dict(up=up)
        if ip:
            logs['ip'] = ip
        self.logfile.write_port_log('wlan', json.dumps(logs))

        if up:
            loop = asyncio.get_event_loop()
            if self.handle:
                self.handle.cancel()
                self.handle = loop.call_soon(self.trigger_upload)

    async def upload_file(self, filename, report_name=None):
        report_name = report_name or os.path.basename(filename)
        bus_id = self.config.get_bus_id()
        timestamp = int(datetime.datetime.now().timestamp())
        with open(filename) as f:
            body = f.read()

        http_client = AsyncHTTPClient()
        req = HTTPRequest(
            url='https://bus-node.humminglab.io/api/v1/bus/{}/timestamp/{}/log/{}'.format(bus_id, timestamp, report_name),
            method='POST',
            body=body)
        try:
            response = await http_client.fetch(req)
        except Exception as e:
            logging.error('Upload Error: %s' % e)
            raise
        else:
            logging.info('Upload OK - %s' % os.path.basename(filename))

    async def upload_files(self, file_infos):
        now = datetime.datetime.now()
        now_str = now.strftime('%Y%m%d-%H%M%S')
        await self.upload_file(DEFAULT_CONFIG_FILENAME, 'config-{}.ini'.format(now_str))
        for finfo in file_infos:
            await self.upload_file(finfo['name'])
            os.unlink(finfo['name'])

    def gather_and_upload(self):
        self.logfile.new_log()
        file_infos = self.logfile.get_old_sys_logs()
        file_infos.extend(self.logfile.get_old_port_logs())
        asyncio.ensure_future(self.upload_files(file_infos))

    def trigger_upload(self):
        loop = asyncio.get_event_loop()
        self.handle = loop.call_later(MIN_REPORT_INTERVAL_SECS, self.trigger_upload)

        addrs = netifaces.ifaddresses(WLAN)
        if not netifaces.AF_INET in addrs:
            logger.info('Upload cancel: WiFi Disconnected')
            return

        if not self.config.get_bus_id():
            return

        now = datetime.datetime.now()
        delta = now - self.last_update_time

        if delta.total_seconds() > MIN_REPORT_INTERVAL_SECS:
            self.gather_and_upload()
            self.last_update_time = datetime.datetime.now()
