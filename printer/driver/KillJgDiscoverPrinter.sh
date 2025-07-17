#!/bin/bash
#Kill the Jaguar Network Printer Discovery application

pid=$(ps -aux | grep $1 | grep JgDiscoverPrinter | awk '{ print $2 }') #kill the errordlg
kill -9 $pid
