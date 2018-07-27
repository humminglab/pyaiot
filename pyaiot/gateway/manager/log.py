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

"""Device Logs"""

import os
import glob
import datetime

LOG_BASE = "{}/.pyaiot/log".format(os.path.expanduser("~"))


def log_time():
    now = datetime.datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    return now_str


class Log():
    def __init__(self):
        self.sys_log_name = None
        self.port_log_name = None
        self.sys_log = None
        self.port_log = None
        self.sys_log_cnt = 0
        self.port_log_cnt = 0

        if not os.path.exists(LOG_BASE):
            os.makedirs(LOG_BASE)

        self.new_log()

    def new_log(self):
        """Create new logfile

        If opened file is empty, reuse it
        """
        now = datetime.datetime.now()
        now_str = now.strftime('%Y%m%d-%H%M%S')

        if self.sys_log is None or self.sys_log_cnt > 0:
            if self.sys_log:
                self.sys_log.close()
            self.sys_log_name = LOG_BASE + '/system-' + now_str + '.log'
            self.sys_log = open(self.sys_log_name, 'w', 1)
            self.sys_log_cnt = 0

        if self.port_log is None or self.port_log_cnt > 0:
            if self.port_log:
                self.port_log.close()
            self.port_log_name = LOG_BASE + '/port-' + now_str + '.log'
            self.port_log = open(self.port_log_name, 'w', 1)
            self.port_log_cnt = 0

    def get_old_syslogs(self):
        """Get system log filenames except current one """
        files = glob.glob(LOG_BASE + '/system-*.log')
        files = filter(lambda f: f != self.sys_log_name, files)
        return files

    def get_old_portlogs(self):
        """Get port log filenames except current one"""
        files = glob.glob(LOG_BASE + '/port-*.log')
        files = filter(lambda f: f != self.port_log_name, files)
        return files

    def write_sys_log(self, log_type, log_str):
        self.sys_log_cnt += 1
        self.sys_log.write(log_time() + ' ' + log_type + ' ' + log_str + '\n')

    def write_port_log(self, log_type, log_str):
        self.port_log_cnt += 1
        self.port_log.write(log_time() + ' ' + log_type + ' ' + log_str + '\n')
