#!/bin/sh
#process commandline argument $1
#syntax ./install.sh <ipaddress> model

echo "Parameter - IP adress " $1
echo "Parameter - Printer Model " $2

model="ZC350"
ppdname="ZebraZC350Printer.ppd"
PRINTERIP=""


#Remove Space From the String
PRINTERMODEL="$(echo "${1}" | tr -d '[:space:]')"
ZCMODEL=0
#Check If any PrinterModel is present in $PRINTERMODEL parameter
#If $PRINTERMODEL doesn't contain any Printer model then assign arguments $2 and $1 
echo "PrinterMODEL " $PRINTERMODEL

if echo $PRINTERMODEL | grep -q "ZC100"  
then
    ZCMODEL=0
    PRINTERIP=$(echo $PRINTERMODEL| cut -d'@' -f 2)
elif echo $PRINTERMODEL | grep -q "ZC150"  
then
    ZCMODEL=1
    PRINTERIP=$(echo $PRINTERMODEL| cut -d'@' -f 2)
elif echo $PRINTERMODEL | grep -q "ZC300"  
then
    ZCMODEL=2
    PRINTERIP=$(echo $PRINTERMODEL| cut -d'@' -f 2)
elif echo $PRINTERMODEL | grep -q "ZC350"  
then
    ZCMODEL=3
    PRINTERIP=$(echo $PRINTERMODEL| cut -d'@' -f 2)
else
    ZCMODEL=$2
    PRINTERIP=$1
fi

echo "ZCMODEL is " $ZCMODEL
case $ZCMODEL in

    0)
        echo "Its ZC100"
        model="ZC100"
        ppdname="ZebraZC100Printer.ppd"
        ;;
    1)
        echo "Its ZC150"
        model="ZC150"
        ppdname="ZebraZC150Printer.ppd"
        ;;
    2)
        echo "Its ZC300"
        model="ZC300"
        ppdname="ZebraZC300Printer.ppd"
        ;;
    3)
        echo "Its ZC350"
        model="ZC350"
        ppdname="ZebraZC350Printer.ppd"
        ;;

esac

echo "Zebra-$model-Ethernet-Printer-IP=$PRINTERIP -E -v socket://$PRINTERIP:9100 -m $ppdname"

/usr/sbin/lpadmin -p "Zebra-$model-Ethernet-Printer-IP=$PRINTERIP" -E -v "socket://$PRINTERIP:9100" -m $ppdname
/etc/init.d/cups restart
