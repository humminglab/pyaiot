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
import os.path
import configparser
from datetime import datetime

DEFAULT_CONFIG_FILENAME = '{}/.pyaiot/config.ini'.format(os.path.expanduser('~'))

logger = logging.getLogger("pyaiot.manager.sync")

class Config():
    """Database for Bus Gateway"""
    def __init__(self):
        logging.info('Start Initial Setup')
        self.config = configparser.ConfigParser()
        self.config.read(DEFAULT_CONFIG_FILENAME)

        self.total_seats = self.config.getint('Config', 'total_seats', fallback=1)
        self.bus_id = self.config.get('Config', 'bus_id', fallback='')

    def get_all_devices(self):
        """Get all device information"""
        seats = []
        for i in range(1, self.total_seats + 1):
            data = self.config.get('Seats', str(i), fallback='')
            data = data.split(',')
            if len(data) == 2:
                seats.append({'seat_number':i, 'device_id':data[0], 'group_number':ord(data[1][0]) - ord('A') + 1})

        return seats

    def get_total_seat(self):
        return self.total_seats

    def get_bus_id(self):
        return self.bus_id