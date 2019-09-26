# Copyright 2017 IoT-Lab Team
# Contributor(s) : see AUTHORS file
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

"""pyaiot package installation module."""

import os
from os.path import join as pjoin
from setuptools import setup, find_packages


PACKAGE = 'pyaiot'


def readme(fname):
    """Utility function to read the README. Used for long description."""
    return open(os.path.join(os.path.dirname(__file__), fname),
                encoding='utf-8').read()


def get_version(package):
    """Extract package version without importing file.

    Inspired from pep8 setup.py.
    """
    with open(os.path.join(package, '__init__.py')) as init_fd:
        for line in init_fd:
            if line.startswith('__version__'):
                return eval(line.split('=')[-1])

if __name__ == '__main__':

    setup(name=PACKAGE,
          version=get_version(PACKAGE),
          description=('Pyaiot based IoT gateway that manages charging nodes'),
          long_description=readme('README.md'),
          author='HummingLab',
          author_email='yslee@humminglab.io',
          url='http://www.humminglab.io',
          license='BSD',
          keywords="iot demonstration web coap mqtt",
          platforms='any',
          packages=find_packages(),
          scripts=[pjoin('bin', 'aiot-broker'),
                   pjoin('bin', 'aiot-manager'),
                   pjoin('bin', 'aiot-coap-gateway'),
                   pjoin('bin', 'aiot-mqtt-gateway'),
                   pjoin('bin', 'aiot-ws-gateway'),
                   pjoin('bin', 'aiot-dashboard'),
                   pjoin('bin', 'aiot-generate-keys')],
          install_requires=[
            'tornado>=5.0',
            'aiocoap>=0.3',
            'hbmqtt>=0.8',
            'cryptography>=2.1.4',
            'pycrypto>=2.6.1',
            'pyserial-asyncio',
            'netifaces',
            'pyroute2'
          ],
          classifiers=[
            'Development Status :: 3 - Alpha',
            'Programming Language :: Python :: 3 :: Only',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Intended Audience :: Developers',
            'Environment :: Console',
            'Topic :: Communications',
            'License :: OSI Approved :: ',
            'License :: OSI Approved :: BSD License'],
          zip_safe=False,
          )
