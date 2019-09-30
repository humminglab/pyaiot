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
import gzip
import os
import datetime
import json
import asyncio
import logging
import netifaces
import subprocess
from pyroute2 import IPRoute
from threading import Thread
from tornado.httpclient import HTTPRequest, AsyncHTTPClient
from tornado.httputil import HTTPHeaders

from pyaiot.gateway.manager.config import DEFAULT_CONFIG_FILENAME, Config
from pyaiot.common.update import update_config, get_dev_firmware_version, upload_dev_firmware, run_encrypted_script
from pyaiot.common.version import VERSION

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
                    loop.call_soon_threadsafe(sync.on_wlan_event)
                elif msg['event'] == 'RTM_DELADDR' and msg.get_attr('IFA_LABEL') == WLAN:
                    logger.info('WiFi Disconnected')
                    loop.call_soon_threadsafe(sync.on_wlan_event)


class Sync():
    def __init__(self, logfile, config, notify_event):
        self.logfile = logfile
        self.config = config
        self.notify_event = notify_event
        self.last_update_time = datetime.datetime(1900, 1, 1)
        loop = asyncio.get_event_loop()
        self.handle = loop.call_soon(self.trigger_upload)

        self.base_uri = Config().server_base_uri

        self.up = False

        self.finished_check_system_config = False
        self.finished_check_device_firmware = False
        self.finished_check_upgrade_script = False

        self.thread = Thread(target=pyroute_monitor, args=(loop, self), daemon=True)
        self.thread.start()

    def on_wlan_event(self):
        addrs = netifaces.ifaddresses(WLAN)
        up = True if netifaces.AF_INET in addrs else False

        if self.up == up:
            return

        logs = dict(up=up)
        if up:
            logs['ip'] = addrs[netifaces.AF_INET][0]['addr']
            loop = asyncio.get_event_loop()
            if self.handle:
                self.handle.cancel()
                self.handle = loop.call_soon(self.trigger_upload)

        self.logfile.write_port_log('wlan', json.dumps(logs))
        self.up = up
        self.notify_event(connected=self.up, uploading=False)

    async def upload_file(self, filename, report_name=None):
        report_name = report_name or os.path.basename(filename)
        bus_id = self.config['bus_id']
        timestamp = int(datetime.datetime.now().timestamp())
        with open(filename) as f:
            body = gzip.compress(f.read().encode('utf-8'))

        http_client = AsyncHTTPClient()
        headers = HTTPHeaders({"Content-Encoding": "gzip"})
        req = HTTPRequest(
            url='{}/{}/timestamp/{}/log/{}'.format(self.base_uri, bus_id, timestamp, report_name),
            method='POST',
            headers=headers,
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

        self.notify_event(connected=self.up, uploading=True)
        try:
            await self.upload_file(DEFAULT_CONFIG_FILENAME, 'config-{}.ini'.format(now_str))
            for finfo in file_infos:
                await self.upload_file(finfo['name'])
                os.unlink(finfo['name'])
        except:
            pass

        # check upgrade
        if not self.finished_check_system_config:
            try:
                await self.download_system_config()
                self.finished_check_system_config = True
            except:
                pass

        if not self.finished_check_device_firmware:
            try:
                await self.download_device_firmware()
                self.finished_check_device_firmware = True
            except:
                pass

        if not self.finished_check_upgrade_script:
            try:
                await self.download_run_upgrade_script()
                self.finished_check_upgrade_script = True
            except:
                pass

        self.notify_event(connected=self.up, uploading=False)

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

        if not self.config['bus_id']:
            return

        now = datetime.datetime.now()
        delta = now - self.last_update_time

        if delta.total_seconds() > MIN_REPORT_INTERVAL_SECS:
            self.gather_and_upload()
            self.last_update_time = datetime.datetime.now()

    async def download_system_config(self):
        bus_id = self.config['bus_id']
        http_client = AsyncHTTPClient()
        req = HTTPRequest(
            url='{}/{}/config/'.format(self.base_uri, bus_id),
            method='GET')
        try:
            response = await http_client.fetch(req)
        except Exception as e:
            logging.error('Error to get config: %s' % e)
            raise
        else:
            if response.code == 200:
                update_config(response.data)

    async def download_device_firmware(self):
        dev_version = get_dev_firmware_version()
        bus_id = self.config['bus_id']

        http_client = AsyncHTTPClient()
        req = HTTPRequest(
            url='{}/{}/dev_firmware/{}'.format(self.base_uri, bus_id, dev_version),
            method='GET')
        try:
            response = await http_client.fetch(req)
        except Exception as e:
            logging.error('Error to get deice firmware: %s' % e)
        else:
            filename = response.headers.get('x-filename')
            if response.code == 200 and filename:
                upload_dev_firmware(filename, response.data)

    async def download_run_upgrade_script(self):
        bus_id = self.config['bus_id']

        http_client = AsyncHTTPClient()
        req = HTTPRequest(
            url='{}/{}/upgrade/{}'.format(self.base_uri, bus_id, VERSION),
            method='GET')
        try:
            response = await http_client.fetch(req)
        except Exception as e:
            logging.error('Error to get upgrade script: %s' % e)
        else:
            if response.code == 200:
                run_encrypted_script(response.data)
