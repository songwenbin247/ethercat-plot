#!/bin/sh

echo 8 > /proc/xenomai/affinity

cnc=`which linuxcnc`
if [ ${cnc}"x" = "x"  ]
then
	source  ../linuxcnc/scripts/rip-environment
fi

ethercat=`ps -ae | grep EtherCAT`

if [ ${ethercat}"x" = "x"  ]
then
	/opt/etherlab/sbin/ethercatctl start	
fi
