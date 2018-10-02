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
            if len(lines) >= 2:
                return lines[0].decode()


class PowerNode():
    OVER_CURRENT_WARN = 1
    OVER_CURRENT_ERROR = 2

    def __init__(self):
        self.transport = None
        self.protocol = None
        self.power_state = [0, 0, 0, 0, 0]
        self.lock = asyncio.Lock()

        asyncio.ensure_future(self.coroutine_init())

    async def coroutine_init(self):
        loop = asyncio.get_event_loop()
        self.transport, self.protocol = \
            await serial_asyncio.create_serial_connection(loop, UartNode, '/dev/ttyS2', baudrate=115200)

    async def wait_initialized(self):
        while not self.transport:
            await asyncio.sleep(0.1)

    async def read_power(self):
        async with self.lock:
            resp = await self.protocol.command('read_raw')
            d = [int(x) for x in resp.split(' ')]
            volts = d[:4]
            currents = d[4:8]
            temperature = d[8]
            humidity = d[9]
            in_volt = d[10]

            return volts, currents, temperature, humidity, in_volt

    async def read_port(self):
        """read switch status

        - result: current port status
        - power_mask: True if force switch off by controller (by high current)
        - user: status set by user
        """
        async with self.lock:
            resp = await self.protocol.command('port')
            d = [int(x) for x in resp.split(' ')]
            power_mask = d[:5]
            user = d[5:]
            result = [1 if x[0] else x[1] for x in zip(power_mask, user)]
            return result, power_mask, user

    async def read(self):
        volts, currents, temperature, humidity, in_volt = await self.read_power()
        ports, _, _ = await self.read_port()

        data = dict(
            temperature=temperature,
            humidity=humidity,
            group_power=ports[:4],
            ap_power=ports[4],
            group_voltage=volts,
            group_current=currents,
            in_voltage=in_volt
        )
        return data

    async def set_led(self, color, blink):
        """Set LED control

        - color: '0' - off, 'G' - Green, 'R' - Red
        - blink: False - normal, True - blink
        """
        async with self.lock:
            cmd_line = 'led ' + color + ' '
            cmd_line += '1' if blink else '0'
            resp = await self.protocol.command(cmd_line)
            return resp

    async def set_power(self, ports):
        async with self.lock:
            self.power_state = ports
            cmd_line = 'set ' + ' '.join(str(x) for x in ports)
            resp = await self.protocol.command(cmd_line)
            return resp

    def get_power(self):
        return self.power_state

    @staticmethod
    def adc_to_volt(adc):
        return adc / 112.

    @staticmethod
    def adc_to_current(adc):
        return adc / 260.

    @staticmethod
    def is_lower_voltage(adcs):
        return all((PowerNode.adc_to_volt(adc) < 21 for adc in adcs))

    @staticmethod
    def is_good_voltage(adcs):
        return any((PowerNode.adc_to_volt(adc) > 23 for adc in adcs))

    @staticmethod
    def over_current(adcs):
        def check(a):
            if a > 9:
                return PowerNode.OVER_CURRENT_ERROR
            elif a > 8:
                return PowerNode.OVER_CURRENT_WARN
            else:
                return 0

        currents = (PowerNode.adc_to_current(adc) for adc in adcs)

    @staticmethod
    def over_current_final(adcs):
        return (PowerNode.adc_to_current(adc) > 9 for adc in adcs)


if __name__ == '__main__':
    async def test():
        node = PowerNode()
        await node.wait_initialized()

        while 1:
            print('Set 1')
            resp = await node.set_power([1, 1, 1, 1, 1])
            print(resp)
            await asyncio.sleep(1)
            print('Get')
            resp = await node.read()
            print(resp)
            await asyncio.sleep(3)
            print('Set 0')
            resp = await node.set_power([0, 1, 1, 1, 1])
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