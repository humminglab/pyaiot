#!/bin/sh

# increase file system
sudo systemctl enable armbian-resize-filesystem.service
# re-enable ntpd for time synchronization
sudo systemctl enable ntp.service


cd /home/pi/project/pyaiot
git fetch && git merge

sync

sudo reboot