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

import os.path
import subprocess
import configparser
from tornado import web
from pyaiot.common.update import update_config, kill_aiot_manager

DEFAULT_CONFIG_FILENAME = '{}/.pyaiot/config.ini'.format(os.path.expanduser('~'))


class ConfigUpdate(web.RequestHandler):
    def post(self):
        file = self.request.files['file'][0]['body']
        filename = self.request.files['file'][0]['filename']

        targets, modified = update_config(file.decode('utf-8'))
        if modified:
            kill_aiot_manager()

        self.write('Updated Fields\n')
        self.write(targets)


class GetSystemInfo(web.RequestHandler):
    def get(self):
        text = ''

        config = configparser.ConfigParser()
        config.read(DEFAULT_CONFIG_FILENAME)
        text += '설정 정보\n'
        try:
            text += 'bus_id: {}\n'.format(config['Config']['bus_id'])
        except:
            pass

        text += '\n네트워크 설정\n'
        r = subprocess.check_output(['nmcli', 'connection', 'show'])
        text += r.decode('utf-8')

        text += '\n무선랜 정보\n'
        r = subprocess.check_output(['nmcli', 'device', 'wifi', 'list'])
        text += r.decode('utf-8')

        text += '\n네트워크 정보\n'
        r = subprocess.check_output(['ifconfig', 'eth0'])
        text += r.decode('utf-8')
        r = subprocess.check_output(['ifconfig', 'wlan0'])
        text += r.decode('utf-8')

        text += '\n디스크 사용량\n'
        r = subprocess.check_output(['df', '-h', '--type=ext4'])
        text += r.decode('utf-8')

        self.write(text)

class GetConf(web.RequestHandler):
    def get(self):
        text = ''
        with open(DEFAULT_CONFIG_FILENAME, 'r') as f:
            text += f.read()

        self.write(text)
