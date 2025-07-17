#!/bin/bash
#Error Notifier for Zebra Jaguar Printer

#CHNAGE LOG
# 01/11/2011 Added $5 to send the Panels remaining in Film as well as Ribbon


if [ $1 = "show" ]  #show msgbox
then

    DISPLAY=:0.0
    export DISPLAY
    XAUTHORITY=/home/$USER/.Xauthority
    export XAUTHORITY
    xhost + >> /dev/null
    /usr/local/ZebraJaguarDriver/JgErrorNotify "$2" "$3" "$4" "$5"
else
    pid=$(ps -aux | grep $1 | grep JgErrorNotify | awk '{ print $2 }') #kill the errordlg
    kill -9 $pid
fi
