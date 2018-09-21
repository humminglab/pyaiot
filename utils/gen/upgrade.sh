#!/bin/sh

add_system_always()
{
  file=$1

  system_field=`grep '^Restart.*always' $file`
  if [ ! $system_field ]; then
    sudo sed -i '/^User/a \Restart=always' $file
  fi
}

# increase file system
sudo systemctl enable armbian-resize-filesystem.service
# re-enable ntpd for time synchronization
sudo systemctl enable ntp.service

cd /home/pi/project/pyaiot
git fetch && git merge

# add Restart field in system service
add_system_always /lib/systemd/system/aiot-broker.service
add_system_always /lib/systemd/system/aiot-coap-gateway.service
add_system_always /lib/systemd/system/aiot-dashboard.service
add_system_always /lib/systemd/system/aiot-manager.service
sudo systemctl daemon-reload


sync

sudo reboot