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
import logging
import datetime

logger = logging.getLogger("pyaiot.manager.log")

LOG_BASE = "{}/.pyaiot/log".format(os.path.expanduser("~"))
MAX_QUOTA = 1*1024*1024*1024
MAX_SYS_LOG_LINE = 2000


def log_time(now):
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    return now_str


class Log():
    def __init__(self):
        self.sys_log_name = None
        self.sys_log = None
        self.sys_log_cnt = MAX_SYS_LOG_LINE
        self.sys_log_last_time = None

        if not os.path.exists(LOG_BASE):
            os.makedirs(LOG_BASE)

        self._fix_logs()
        self.new_log()

    def _delete_zero_length_files(self, file_infos):
        fout = []
        for finfo in file_infos:
            if finfo['stat'].st_size == 0:
                os.unlink(finfo['name'])
            else:
                fout.append(finfo)
        return fout

    def _get_total_size(self, file_infos):
        total = 0
        for finfo in file_infos:
            total += finfo['stat'].st_size
        return total

    def _delete_under_quota(self, total, file_infos):
        while total > MAX_QUOTA and len(file_infos) > 0:
            finfo = file_infos.pop(0)
            total -= finfo['stat'].st_size
            os.unlink(finfo['name'])
        return total

    def _fix_logs(self):
        """delete file if zero length, and remove files if over quota"""
        sys_logs = self.get_old_sys_logs()
        sys_logs = self._delete_zero_length_files(sys_logs)

        total = self._get_total_size(sys_logs)

        # Sequential remove of old files
        self._delete_under_quota(total, sys_logs)

    def new_log(self):
        """Create new logfile

        If opened file is empty, reuse it
        """
        if self.sys_log_cnt == 0:
            return

        now = datetime.datetime.now()
        now_str = now.strftime('%Y%m%d-%H%M%S')

        if self.sys_log:
            self.sys_log.close()
        self.sys_log_name = LOG_BASE + '/system-' + now_str + '.log'
        self.sys_log = open(self.sys_log_name, 'w', 1)
        self.sys_log_cnt = 0
        self.sys_log_last_time = now

    def get_old_sys_logs(self):
        """Get system log filenames except current one """
        files = sorted(glob.glob(LOG_BASE + '/system-*.log'))
        files = filter(lambda f: f != self.sys_log_name, files)
        return [{'name':f, 'stat':os.stat(f)} for f in sorted(files)]

    def get_old_port_logs(self):
        """Get port log filenames except current one"""
        return []

    def write_sys_log(self, log_type, log_str):
        now = datetime.datetime.now()
        if self.sys_log_cnt > MAX_SYS_LOG_LINE or now.date() != self.sys_log_last_time.date():
            self.new_log()

        self.sys_log_cnt += 1
        self.sys_log.write(log_time(now) + ' ' + log_type + ' ' + log_str + '\n')

    def write_port_log(self, log_type, log_str):
        pass
