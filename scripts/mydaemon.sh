#!/bin/bash

LOGFILE=~/my-daemon/daemon.log

echo "Daemon started at $(date)" >> $LOGFILE

while true; do
    echo "Current time: $(date)" >> $LOGFILE
    echo "Current time: $(date)"
    sleep 60
done
