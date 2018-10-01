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
import glob
import subprocess
import logging
import configparser
import tempfile
from pyaiot.common.decrypt import decrypt_file

CONFIG = 'Config'
SEATS = 'Seats'
TOTAL_SEATS = 'total_seats'
BUS_ID = 'bus_id'
SSID = 'ssid'
PSK = 'psk'

DEFAULT_CONFIG_FILENAME = '{}/.pyaiot/config/config.ini'.format(os.path.expanduser('~'))
FIRMWARE_DIR = '{}/.pyaiot/firmware'.format(os.path.expanduser('~'))


def get_dev_firmware_version():
    files = glob.glob('{}/node-*.img'.format(FIRMWARE_DIR))
    if files >= 1:
        filename = os.path.basename(files[0])
        name, ext = os.path.splitext(filename)

        offs = name.find('-')
        if offs < 0:
            return '0'
        else:
            return name[offs:]
    else:
        return '0'


def kill_aiot_manager():
    """kill aiot-manger (re-run it by systemd)"""
    subprocess.call(['killall', '-SIGKILL', 'aiot-manager'])


def update_config(data):
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
    if CONFIG in sections:
        if not config.has_section(CONFIG):
            config.add_section(CONFIG)

        need_wifi_update = False

        for k, v in new_config.items(CONFIG):
            if k == TOTAL_SEATS:
                update(CONFIG, TOTAL_SEATS)

            if k == BUS_ID:
                update(CONFIG, BUS_ID)

            if k[:len(SSID)] == SSID and len(k) == len(SSID)+1:
                update(CONFIG, k)
                need_wifi_update = True

            if k[:len(PSK)] == PSK and len(k) == len(PSK)+1:
                update(CONFIG, k)
                need_wifi_update = True

        if need_wifi_update:
            update_network_manager(config[CONFIG])

    if SEATS in sections:
        total_seats = config.getint(CONFIG, TOTAL_SEATS)

        for k, v in new_config.items(SEATS):
            if str.isnumeric(k) and int(k) <= total_seats:
                update(SEATS, k)

    with open(DEFAULT_CONFIG_FILENAME + '~', 'w') as configfile:
        config.write(configfile)
        os.sync()
        os.rename(DEFAULT_CONFIG_FILENAME + '~', DEFAULT_CONFIG_FILENAME)

    return targets, modified


def update_network_manager(config):
    """Remove all wifi config and add new wifi configuration"""

    # remove all wifi config
    r = subprocess.check_output(['nmcli', 'connection', 'show'])
    r = r.decode('utf-8').split('\n')
    for line in r:
        field = line.split()
        if len(field) >= 4 and field[-2] == 'wifi':
            subprocess.call(['nmcli', 'connection', 'delete', field[-3]])

    for i in range(1, 5):
        ssid = '{}{}'.format(SSID, i)
        psk = '{}{}'.format(PSK, i)

        if ssid in config and psk in config and len(config[ssid]) > 0:
            subprocess.call(['nmcli', 'connection', 'add', 'type', 'wifi', 'con-name',
                             config[ssid], 'ifname', 'wlan0', 'ssid', config[ssid]])

            if len(config[psk]) > 0:
                subprocess.call(['nmcli', 'connection', 'modify', config[ssid],
                                 'ipv4.route-metric', '50', 'ipv6.route-metric', '50',
                                 'wifi-sec.key-mgmt', 'wpa-psk', 'wifi-sec.psk', config[psk]])


def upload_dev_firmware(filename, enc_data):
    """save uploaded new firmware into firmware folder and remove old firmware files

    Filename must be the following format.
     - node-1.0.0.img
    """
    data = decrypt_file(enc_data)

    filename = os.path.basename(filename)
    name, ext = os.path.splitext(filename)

    if len(name) == 0:
        raise TypeError('Too short file name')

    if name.find('-') < 0 or ext != '.img':
        raise TypeError('Invalid firmware file name')

    dev_type, version = name.split('-')
    if dev_type not in ['node'] or len(version) == 0:
        raise TypeError('Invalid firmware file name')

    if not os.path.exists(FIRMWARE_DIR):
        os.mkdir(FIRMWARE_DIR)

    for f in glob.glob('{}/{}*'.format(FIRMWARE_DIR, dev_type)):
        logging.info('Remove old firmware: {}'.format(f))
        os.remove(f)

    with open('{}/{}{}'.format(FIRMWARE_DIR, name, ext), 'wb') as f:
        f.write(data)


def run_encrypted_script(enc_data):
    """Run encrypted shell script for system upgrade"""
    data = decrypt_file(enc_data)
    with tempfile.NamedTemporaryFile() as file:
        file.file.write(data)
        file.file.flush()
        r = subprocess.check_output(['bash', file.name])
        return r.decode('utf-8')

