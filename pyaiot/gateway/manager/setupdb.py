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

"""Power control device"""

import logging
import os
import configparser
try:
    from .database import Database, DEFAULT_DB_FILENAME
except:
    from database import Database, DEFAULT_DB_FILENAME

INIT_SETUP_FILE = "{}/.pyaiot/init_setup.ini".format(os.path.expanduser("~"))

def apply_init_setup(filename=INIT_SETUP_FILE):
    """Verify that filename exists and is correctly formatted."""
    if not os.path.isfile(filename):
        return

    logging.info('Start Initial Setup')
    config = configparser.ConfigParser()
    config.read(filename)

    # drop all tables in database
    if os.path.isfile(DEFAULT_DB_FILENAME):
        os.remove(DEFAULT_DB_FILENAME)

    # rebuild database
    db = Database()

    total_seats = config.getint('CONFIG', 'total_seats', fallback=1)
    db.set_conf('total_seats', total_seats)

    for i in range(1, total_seats+1):
        data = config.get('SEATS', str(i), fallback='')
        data = data.split(',')
        if len(data) != 2:
            continue

        db.set_device({
            'seat_number': i,
            'device_id': data[0],
            'group_number': ord(data[1][0]) - ord('A') + 1,
        })

    config = None
    db = None
    os.remove(filename)
    logging.info('Finish Initial Setup Successfully')
