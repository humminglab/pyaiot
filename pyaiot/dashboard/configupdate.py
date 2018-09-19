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

import os
import os.path
import subprocess
import configparser
from tornado import web

DEFAULT_CONFIG_FILENAME = '{}/.pyaiot/config.ini'.format(os.path.expanduser('~'))


class ConfigUpdate(web.RequestHandler):
    def post(self):
        file = self.request.files['file'][0]['body']
        filename = self.request.files['file'][0]['filename']

        targets = self.update_config(filename, file.decode('utf-8'))
        self.write('Updated Fields\n')
        self.write(targets)

    def update_config(self, filename, data):
        """update configuration files and reload tornado"""
        modified = False
        targets = ''

        config = configparser.ConfigParser()
        config.read(DEFAULT_CONFIG_FILENAME)
        new_config = configparser.ConfigParser()
        new_config.read_string(data)

        def update(sec, option):
            if not config.has_option(sec, option) or config[sec][option] != new_config[sec][option]:
                nonlocal modified, targets
                old_val = config[sec][option] if config.has_option(sec, option) else ''
                targets += '{}, {}: {} => {}\n'.format(sec, option, old_val, new_config[sec][option])
                config[sec][option] = new_config[sec][option]
                modified = True
                return True
            else:
                return False

        sections = new_config.sections()
        CONFIG = 'Config'
        SEATS = 'Seats'
        TOTAL_SEATS = 'total_seats'
        BUS_ID = 'bus_id'
        SSID = 'ssid'
        PSK = 'psk'
        if CONFIG in sections:
            if not config.has_section(CONFIG):
                config.add_section(CONFIG)

            need_wifi_update = False

            for k, v in new_config.items(CONFIG):
                if k == TOTAL_SEATS:
                    update(CONFIG, TOTAL_SEATS)

                if k == BUS_ID:
                    update(CONFIG, BUS_ID)

                if k == SSID and update(CONFIG, SSID):
                    need_wifi_update = True

                if k == PSK and update(CONFIG, PSK):
                    need_wifi_update = True

            if need_wifi_update:
                self.update_network_manager(config[CONFIG][SSID], config[CONFIG][PSK])

        if SEATS in sections:
            total_seats = config.getint(CONFIG, TOTAL_SEATS)

            for k, v in new_config.items(SEATS):
                if str.isnumeric(k) and int(k) <= total_seats:
                    update(SEATS, k)

        # kill aiot-manger
        if modified:
            with open(DEFAULT_CONFIG_FILENAME + '~', 'w') as configfile:
                config.write(configfile)

            os.sync()
            os.rename(DEFAULT_CONFIG_FILENAME + '~', DEFAULT_CONFIG_FILENAME)

            subprocess.call(['killall', '-SIGKILL', 'aiot-manager'])
        return targets

    def update_network_manager(self, ssid, psk):
        """Remove all wifi config and add new wifi configuration"""

        # remove all wifi config
        r = subprocess.check_output(['nmcli', 'connection', 'show'])
        r = r.decode('utf-8').split('\n')
        for line in r:
            field = line.split()
            if len(field) >= 4 and field[-2] == '802-11-wireless':
                subprocess.call(['nmcli', 'connection', 'delete', field[-3]])

        subprocess.call(['nmcli', 'connection', 'add', 'type', 'wifi', 'con-name',
                         ssid, 'ifname', 'wlan0', 'ssid', ssid])

        subprocess.call(['nmcli', 'connection', 'modify', ssid, 'wifi-sec.key-mgmt',
                         'wpa-psk', 'wifi-sec.psk', psk])


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

        self.write(text)
