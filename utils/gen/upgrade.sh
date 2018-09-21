#!/bin/sh

sudo systemctl enable armbian-resize-filesystem.service

cd /home/pi/project/pyaiot
git fetch && git merge

sync

sudo reboot