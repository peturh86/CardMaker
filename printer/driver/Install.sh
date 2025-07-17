#!/bin/sh
# $1 install or uninstall 
SERVICENAME="JgPPDConfig"

install_files()
{
    # Copy filter files from current directory
    cp -v pdftojgpdf       /usr/lib/cups/filter/
    cp -v rastertojg       /usr/lib/cups/filter/
    
    # Copy backend from current directory
    cp -v zcusb            /usr/lib/cups/backend/
    
    # Copy udev rules from current directory  
    cp -v *.rules          /lib/udev/rules.d/
    cp -v JgPnP            /lib/udev/
    
    # Copy PPD files from current directory
    cp -vf *.ppd           /usr/share/cups/model/
    
    # Set permissions
    chmod 755 /usr/lib/cups/filter/rastertojg
    chmod 755 /usr/lib/cups/filter/pdftojgpdf
    chmod 755 /usr/lib/cups/backend/zcusb 

    # Create log directories
    mkdir -p  /var/log/JaguarLog/
    chmod 755 /var/log/JaguarLog/
    mkdir -p /usr/local/ZebraJaguarDriver/config
    chmod 755 /usr/local/ZebraJaguarDriver/config

    # Install libraries
    if [ -f /usr/lib/x86_64-linux-gnu/libtinyxml.so.2.6.2 ]
    then
        echo "libtinyxml Library File Exists"
    else
        cp -v libtinyxml.so.2.6.2 /usr/lib/x86_64-linux-gnu/libtinyxml.so.2.6.2
        echo "libtinyxml Library File Copied"
    fi
    
    cp -v libzmjxml.so /usr/lib
    echo "libzmjxml Library File Copied"
}

install_files