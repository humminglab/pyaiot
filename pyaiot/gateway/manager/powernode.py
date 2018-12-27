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

from pyaiot.gateway.manager.config import Config

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

    def __init__(self, config):
        self.config = config
        self.transport = None
        self.protocol = None
        self.power_state = [0, 0, 0, 0, 0]
        self.lock = asyncio.Lock()
        self.version = ''

        self.current_scale = self.config['current_scale']
        self.voltage_scale = self.config['voltage_scale']
        self.over_current = self.config['over_current']
        self.warn_current = self.config['warn_current']
        self.low_voltage = self.config['low_voltage']
        self.normal_voltage = self.config['normal_voltage']
        self.low_voltage_hold_time = self.config['low_voltage_hold_time']

        asyncio.ensure_future(self.coroutine_init())

    async def coroutine_init(self):
        loop = asyncio.get_event_loop()
        self.transport, self.protocol = \
            await serial_asyncio.create_serial_connection(loop, UartNode, '/dev/ttyS2', baudrate=115200)

    async def wait_initialized(self):
        while not self.transport:
            await asyncio.sleep(0.1)

        async with self.lock:
            self.version = await self.protocol.command('version')

        await self.set_over_current_level(int(self.over_current * self.current_scale))

    async def read_power(self):
        """Read ADC level (voltage, current, temp, humi)

        - volts: Group 1~4 voltage (ADC value)
        - currents Group 1~4 current (ADC value)
        - temperature: ADC value
        - humidity: ADC value
        - in_volt: input voltage (ADC value)
        """
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
        - user: status set by user (self.set_power)
        """
        async with self.lock:
            resp = await self.protocol.command('port')
            d = [int(x) for x in resp.split(' ')]
            power_mask = d[:5]
            power = d[5:]
            result = [1 if x[0] else x[1] for x in zip(power_mask, power)]
            return result, power_mask, power

    async def read(self):
        volts, currents, temperature, humidity, in_volt = await self.read_power()
        ports, power_mask, power = await self.read_port()

        data = dict(
            temperature=temperature,
            humidity=humidity,
            group_power=ports[:4],
            ap_power=ports[4],
            group_voltage=volts,
            group_current=currents,
            in_voltage=in_volt,
            power_mask=power_mask,
            power=power
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

    async def set_pled(self, color, blink):
        """Set Power Error LED control

        - color: '0' - off, 'G' - Green, 'R' - Red
        - blink: False - normal, True - blink
        """
        async with self.lock:
            cmd_line = 'pled ' + color + ' '
            cmd_line += '1' if blink else '0'
            resp = await self.protocol.command(cmd_line)
            return resp

    async def set_power(self, ports):
        """Set Power on/off

        :param ports: 5 elements array (G1~G4, AP)
        """
        async with self.lock:
            self.power_state = ports
            cmd_line = 'set ' + ' '.join(str(x) for x in ports)
            resp = await self.protocol.command(cmd_line)
            return resp

    async def set_power_mask(self, masks):
        """Reset Overcurrent Mask

        :param masks: 5 elemenets array (G1~G4, AP). 1 is power masked(OFF)
        """
        async with self.lock:
            cmd_line = 'mask ' + ' '.join(str(x) for x in masks)
            resp = await self.protocol.command(cmd_line)
            return resp

    async def set_over_current_level(self, level):
        """Set new over current cut-off level

        :param level: ADC level for current limit
        """
        async with self.lock:
            cmd_line = 'over_current %d' % (level)
            resp = await self.protocol.command(cmd_line)
            return resp

    def get_cached_power(self):
        return self.power_state

    def adc_to_volt(self, adc):
        return float(adc) / self.voltage_scale

    def adc_to_current(self, adc):
        return float(adc) / self.current_scale

    def is_lower_voltage(self, adc):
        return self.adc_to_volt(adc) < self.low_voltage

    def is_good_voltage(self, adc):
        return self.adc_to_volt(adc) > self.normal_voltage

    def check_over_current(self, adcs):
        def check(a):
            if a > self.over_current:
                return PowerNode.OVER_CURRENT_ERROR
            elif a > self.warn_current:
                return PowerNode.OVER_CURRENT_WARN
            else:
                return 0

        currents = (self.adc_to_current(adc) for adc in adcs)

    def over_current_final(self, adcs):
        return (PowerNode.adc_to_current(adc) > self.over_current for adc in adcs)


if __name__ == '__main__':
    async def test():
        node = PowerNode(Config())
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