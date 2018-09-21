#!/bin/sh

add_system_always()
{
  file=$1

  system_field=`grep '^Restart.*always' $file`
  if [ ! $system_field ]; then
    sudo sed -i '/^User/a \Restart=always' $file
  fi
}

set -e

# increase file system
echo 'Expand file system space'
sudo systemctl enable armbian-resize-filesystem.service
# re-enable ntpd for time synchronization
echo 'Enable NTP server'
sudo systemctl enable ntp.service

echo 'Update git'
cd /home/pi/project/pyaiot
git fetch && git merge

# add Restart field in system service
echo 'Fix aiot service'
set +e
add_system_always /lib/systemd/system/aiot-broker.service
add_system_always /lib/systemd/system/aiot-coap-gateway.service
add_system_always /lib/systemd/system/aiot-dashboard.service
add_system_always /lib/systemd/system/aiot-manager.service
set -e
sudo systemctl daemon-reload

echo 'Sync'
sync

echo 'Reboot'
((sleep 5; sudo reboot)&)&
