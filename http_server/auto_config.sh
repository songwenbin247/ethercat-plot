#!/bin/bash

log_rec()
{
	if [ -e $2 ]
     		then
             	rm $2
     	fi
     	touch $2      
	echo "start read"
     	while read -r line;
     	do
	     echo -n "-->"
             echo $line >> $2 

	done < "$1"
}

send_command()
{
	log_rec $1 "$3" & bgPid=$!
	echo $2 > $1
        sleep $4
	kill $bgPid
        sleep 0.2
}

if [[ $# -lt 1 ]]; then
    echo "Usage:"
    echo "  auto_config.sh <option> [....] "
    echo "  Options: "
    echo "  	init [tty devices]"
    echo " 	  Initialize all devices to default status."
    echo "           Default status: "
    echo "               Switch1: tsn on"
    echo "               Switch2: tsn on"
    echo "               	  ech2 up and ip 192.168.20.1 "
    echo "               	  iperf server up"
    echo "               Ls1043ardb: fm1-mac6 up and ip 192.168.20.1"
    echo "               	     iperf client waitting start "
    echo "           tty devies:"
    echo "               Set tty port ID. " 
    echo "                 Default: /dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2"
    echo "  	tsn [on/off]"
    echo "         Set tsn status"
    echo "  	stream [on/off]"
    echo "         Set background stream status"
    echo "      send [device] [cmd]"
    echo "         Send shell cmd to device"
    echo "         device: SW1 SW2 LS"
    exit 1
fi

# Exit when any command fails

if [ -e auto_config.conf ]; then
	read -r line < auto_config.conf
	tty_devices=($line)
else
	tty_devices=(/dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2)
fi

tty_SW1=${tty_devices[0]}
tty_SW2=${tty_devices[1]}
tty_LS=${tty_devices[2]}


if [ x$1 = xinit ]
then
	if [ $# != 1 ] && [ $# != 4 ]
	then
		echo "Error: run ./auto_config.sh to get help  "
		exit
	fi
	
	if [ $# = 4 ]
	then
		tty_devices=($2 $3 $4)
	fi
	
	for i in ${tty_devices[@]}
	do 
		stty -F $i raw -echo 115200
		echo "root" > $i
		sleep 1
		echo "hostname" > $i && read -r line < $i && read -r line < $i
		line=${line:0:7}
		case "$line" in
			"OpenIL1")
			 tty_SW1=$i
			 echo "Set host($line) tty_id to $i"
			 ;;
			"OpenIL2")
			 tty_SW2=$i
			 echo "Set host($line) tty_id to $i"
			 ;;
			"ls1043a")
			 tty_LS=$i
			 echo "Set host($line) tty_id to $i"
                         ;;
			*)
				echo "Error: cann't recognize the host ($line)"
			exit 1
		esac
      	done
	
	echo $tty_SW1 $tty_SW2 $tty_LS > auto_config.conf
	echo "Set TSN on"
	echo "sja1105-tool config load /root/ls1021_tsn_config/qbv_ethercat_switch1.xml " > $tty_SW1
	echo "sja1105-tool config load /root/ls1021_tsn_config/qbv_ethercat_switch2.xml " > $tty_SW2
	echo "Set ipertf..."
	echo "ifconfig eth2 192.168.2.1"  > $tty_SW2
	sleep 5
	echo "iperf -s -D" > $tty_SW2
	echo "ifconfig fm1-mac6 192.168.2.3" > $tty_LS
	
elif [ x$1 = xtsn ]; then
	if [ x$2 = xoff ]; then
		echo "sja1105-tool config load /root/ls1021_tsn_config/ethercat_switch1_init.xml " > $tty_SW1
		echo "sja1105-tool config load /root/ls1021_tsn_config/ethercat_switch2_init.xml " > $tty_SW2
	else
		echo "sja1105-tool config load /root/ls1021_tsn_config/qbv_ethercat_switch1.xml " > $tty_SW1
		echo "sja1105-tool config load /root/ls1021_tsn_config/qbv_ethercat_switch2.xml " > $tty_SW2
	fi
	sleep 1
	echo "sja1105-tool config upload " > $tty_SW1
	echo "sja1105-tool config upload " > $tty_SW2
elif [ x$1 = xstream ]; then
        send_command $tty_LS "ps -e | grep iperf" auto_config.send.log 1
	pid=""
        while read -r line;
        do
            echo $line

		echo line = $line
		line=($line)
		if [ -n ${line[0]} ] && [ "${line[0]}" -eq "${line[0]}" ] 2>/dev/null; then
			stream_s=on
			pid=${line[0]} 
		else
			stream_s=off
		fi
        done < auto_config.send.log
	echo $stream_s

	if [ x$2 = xoff ]; then
		if [ x$stream_s = xon ]; then
			#echo "kill $line" > $tty_LS
			echo kill ${pid}
			send_command $tty_LS "kill ${pid}" auto_config.send.log 1
			while read -r line;
			do
				echo $line 
			done < auto_config.send.log
		else
			echo "Cann't find iperf pid"
		fi

	else
		if [ x$stream_s = xoff ]; then
		   echo "iperf -c 192.168.2.1 -l 400B -b 800M -t 80000&" > $tty_LS
		fi
	fi
elif [ x$1 = xsend ]; then
	if [ $# != 4 ]; then
		echo "Error: run ./auto_config.sh to get help  "
		exit 1
	else
		typeset -n tty_id=tty_$2
		send_command ${tty_id} "$3" auto_config.send.log $4
		while read -r line;
		do
			echo $line
		done < auto_config.send.log

	fi
fi




