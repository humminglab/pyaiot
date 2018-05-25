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
import sqlite3
from datetime import datetime

DEFAULT_DB_FILENAME = "{}/.pyaiot/pyaiot.db".format(os.path.expanduser("~"))

def to_bitmap(array):
    l = []
    for i in array:
        l.append(str(i))
    return ''.join(l)

def count_nonzero(array):
    count = 0
    for i in array:
        count += int(bool(i))
    return count

def count_zero(array):
    count = 0
    for i in array:
        count += int(not i)
    return count

def to_string(data):
    if type(data) == list or type(data) == tuple:
        return ','.join(str(int(x)) if type(x) is bool else str(x) for x in data)
    return data

class Database():
    """Database for Bus Gateway"""
    def __init__(self):
        self.lock_count = 0
        self.conn = sqlite3.connect(DEFAULT_DB_FILENAME)
        self.cursor = self.conn.cursor()
        self.check_database()

    def get_all_devices(self):
        """Get all device information"""
        devices = []
        self.cursor.execute('SELECT * FROM devices ORDER BY seat_number ASC')
        for i in self.cursor:
            dev = dict(
                db_id=i[0],
                device_id=i[1],
                seat_number=i[2],
                group_number=i[3])
            devices.append(dev)
        return devices

    def set_device(self, dev):
        """Update of insert device information"""
        self.cursor.execute('SELECT id FROM devices WHERE device_id == ?', (dev['device_id'],))
        entry = self.cursor.fetchone()
        if entry:
            self.cursor.execute('UPDATE devices SET seat_number=?, group_number=? WHERE id=?',
                                (dev['seat_number'], dev['group_number'], entry[0]))
        else:
            self.cursor.execute('INSERT INTO devices (device_id, seat_number, group_number) VALUES (?, ?, ?)',
                                (dev['device_id'], dev['seat_number'], dev['group_number']))
        self.conn.commit()

    def delete_device(self, device_id):
        """Delete device ID"""
        self.cursor.execute('SELECT id FROM devices WHERE device_id == ?', (device_id,))
        entry = self.cursor.fetchone()
        if not entry:
            return

        self.cursor.execute('DELETE FROM devices WHERE id == ?', (entry[0],))
        self.cursor.execute('DELETE FROM dev_logs WHERE device == ?', (entry[0],))
        self.conn.commit()

    def insert_log(self, log):
        """Insert log into logs table"""
        self.cursor.execute('INSERT INTO logs (timestamp, temperature, humidity, port_total, port_fault, port_charging, '
                            'port_fault_detail, port_charging_detail, system_fault, port_fast_charge_detail, power_on, '
                            'voltage_average, current_sum, voltage_1, voltage_2, voltage_3, voltage_4, current_1, '
                            'current_2, current_3, current_4) '
                            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                            (
                                log['timestamp'] if 'timestamp' in log else datetime.now().timestamp(),
                                log['temperature'], log['humidity'], len(log['port_fault']),
                                count_nonzero(log['port_fault']), count_nonzero(log['port_charging']),
                                to_bitmap(log['port_fault']), to_bitmap(log['port_charging']),
                                log['system_fault'], to_bitmap(log['port_fast_charge']),
                                to_bitmap(log['power_on']),
                                sum(log['voltage']) / float(len(log['voltage'])),
                                sum(log['current']),
                                log['voltage'][0], log['voltage'][1], log['voltage'][2], log['voltage'][3],
                                log['current'][0], log['current'][1], log['current'][2], log['current'][3]
                            ))
        self.conn.commit()

    def insert_port_log(self, key, value, device_id):
        """Insert port log int dev_logs"""
        print(key, value, type(value), to_string(value), device_id)
        self.cursor.execute('INSERT INTO dev_logs (timestamp, device_id, key, value) VALUES (?,?,?,?)',
                            (datetime.now().timestamp(), device_id, key, to_string(value)))

    def throw_old_logs(self, before):
        """Remove log from database until 'before'"""
        self.cursor.execute('DELETE FROM logs WHERE timestamp < ?', (before,))
        self.conn.commit()

    def throw_old_port_logs(self, before):
        """Remvoe port log from database until 'before' """
        self.cursor.execute('DELETE FROM device_logs WHERE timestamp < ?', (before,))
        self.conn.commit()

    def get_conf(self, name, default):
        self.cursor.execute('SELECT value FROM configs WHERE name == ?', (name,))
        result = self.cursor.fetchone()
        return result[0] if result else default

    def set_conf(self, name, value):
        self.cursor.execute('UPDATE configs SET value=? WHERE name=?', (value, name))
        if self.cursor.rowcount < 1:
            self.cursor.execute('INSERT INTO configs (name, value) VALUES (?, ?)', (name, value))
        self.conn.commit()

    def check_database(self):
        """Check db tabel and create if not existed"""
        self.cursor.execute('SELECT name FROM sqlite_master WHERE type == ?', ('table',))
        entries = self.cursor.fetchall()

        if ('devices',) not in entries:
            self.cursor.execute('CREATE TABLE devices ('
                                'id INTEGER PRIMARY KEY AUTOINCREMENT,'
                                'device_id TEXT NOT NULL UNIQUE,'
                                'seat_number INTEGER NOT NULL UNIQUE,'
                                'group_number INTEGER NOT NULL)')

        if ('logs',) not in entries:
            self.cursor.execute('CREATE TABLE logs ('
                                'id INTEGER PRIMARY KEY AUTOINCREMENT,'
                                'timestamp NUMERIC NOT NULL,'
                                'temperature INTEGER NOT NULL,'
                                'humidity INTEGER NOT NULL,'
                                'port_total INTEGER NOT NULL,'
                                'port_fault INTEGER NOT NULL,'
                                'port_charging INTEGER NOT NULL,'
                                'port_fault_detail TEXT NOT NULL,'
                                'port_charging_detail TEXT NOT NULL,'
                                'system_fault INTEGER NOT NULL,'
                                'port_fast_charge_detail TEXT NOT NULL,'
                                'power_on TEXT NOT NULL,'
                                'voltage_average REAL NOT NULL,'
                                'current_sum REAL NOT NULL,'
                                'voltage_1 REAL,'
                                'voltage_2 REAL,'
                                'voltage_3 REAL,'
                                'voltage_4 REAL,'
                                'current_1 REAL,'
                                'current_2 REAL,'
                                'current_3 REAL,'
                                'current_4 REAL)')

        if ('dev_logs',) not in entries:
            self.cursor.execute('CREATE TABLE dev_logs ('
                                'id INTEGER PRIMARY KEY AUTOINCREMENT,'
                                'timestamp NUMERIC NOT NULL,'
                                'device_id TEXT NOT NULL,'
                                'key TEXT NOT NULL,'
                                'value TEXT)')

        if ('configs', ) not in entries:
            self.cursor.execute('CREATE TABLE configs ('
                                'name TEXT NOT NULL UNIQUE,'
                                'value TEXT)')

        self.conn.commit()
