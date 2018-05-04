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
import asyncio
import serial_asyncio

logger = logging.getLogger("pyaiot.gw.powernode")


class UartNode(asyncio.Protocol):
    def connection_made(self, transport):
        transport.serial.rts = False
        logger.info('Power Node Created')
        self.transport = transport
        self.queue = asyncio.Queue()

    def data_received(self, data):
        self.queue.put_nowait(data)

    async def command(self, cmd_line):
        timeout = 3.0
        buf = b''
        while not self.queue.empty():
            await self.queue.get()

        cmd_line += '\r\n'
        self.transport.write(cmd_line.encode())

        while 1:
            buf += await asyncio.wait_for(self.queue.get(), timeout)
            if len(buf) > 1000:
                raise OverflowError

            lines = buf.split(b'\r\n')
            if len(lines) >= 3:
                return lines[1].decode()

class PowerNode():
    def __init__(self):
        self.transport = None
        self.protocol = None
        self.lock = asyncio.Lock()

        asyncio.ensure_future(self.coroutine_init())

    async def coroutine_init(self):
        loop = asyncio.get_event_loop()
        self.transport, self.protocol = \
            await serial_asyncio.create_serial_connection(loop, UartNode, '/dev/ttyS2', baudrate=115200)

    async def wait_initialized(self):
        while not self.transport:
            await asyncio.sleep(0.1)

    async def read(self):
        async with self.lock:
            resp = await self.protocol.command('read')
            d = [int(x) for x in resp.split(' ')]
            data = dict(
                temperature = d[0],
                humidity = d[1],
                group_power = [bool(x) for x in d[2:6]],
                ap_power = bool(d[6]),
                group_voltage = d[7:11],
                group_current = d[11:15]
            )
            return data

    async def set(self, ports):
        async with self.lock:
            cmd_line = 'set ' + ' '.join(str(x) for x in ports)
            resp = await self.protocol.command(cmd_line)
            data = [bool(int(x)) for x in resp.split(' ')]
            return data

if __name__ == '__main__':
    async def test():
        node = PowerNode()
        await node.wait_initialized()

        while 1:
            print('Set 1')
            resp = await node.set([1,1,1,1,1])
            print(resp)
            await asyncio.sleep(1)
            print('Get')
            resp = await node.read()
            print(resp)
            await asyncio.sleep(3)
            print('Set 0')
            resp = await node.set([0,1,1,1,1])
            print(resp)
            await asyncio.sleep(1)
            print('Get')
            resp = await node.read()
            print(resp)
            await asyncio.sleep(3)

    asyncio.ensure_future(test())
    loop = asyncio.get_event_loop()
    loop.run_forever()
    loop.close()