#!/bin/sh

# this script compares current firmware version of ReXgen device
# with available firmwares in /home/root/rexusb/firmware folder.
# it can use with or not a parameter
# 		reflash new firmware and reboot
# 1	 	ask to manually reflash new firmware
# 2		just reflash new firmware without reboot 
# also checks value of REFLASH_NEW_FRM variable in /data/mender/deployment.conf
# and takes proper action.

#get_frm_num() {
#	VER=$1
#	VER="${VER//[!1234567890.]/}"
#	VER=$(echo "$VER" | sed 's/\./ /g')
#
#	read -ra ARR <<< $VER
#	N=${#ARR[@]}
#	RES=$(echo "0" | tr -dc '0-9')
#	K=$(echo "65025" | tr -dc '0-9')
#	for (( i=0; i<$N; i++ )); do	
#		VAL=$(echo "${ARR[i]}" | tr -dc '0-9')
#		RES=$((RES + VAL*K))
#		K=$((K/255))	
#	done
#}

# comment this if mender support implemented
#ACTION="ask" 

# uncomment this if mender support implemented
#ACTION="never"
#if [[ -f /data/mender/deployment.conf ]]; then
#	ACTION=$(cat /data/mender/deployment.conf | grep REFLASH_NEW_FRM | awk -F'=' '{print $NF}')
#fi
#if [[ ACTION == "never" ]]; then
#	exit
#fi

#FRM_DIR="/home/root/rexusb/firmware"
#INF_DIR="/opt/influx"

#if [[ $1 == "2" ]]; then 
#	OLD_FRM=$(cat /data/mender/firmware)
#else
#	OLD_FRM=$(rexgen firmware)
#fi
#get_frm_num "$OLD_FRM"
#OLD_FRM=$((RES))
#NEW_FRM=$((0))
#NEW_FN=""

#ls -1 /home/root/rexusb/firmware/firmware*.bin | sed 's#.*/##' > "$INF_DIR"/frm_files.txt
#while read FRM_FILE; do
#	get_frm_num "$FRM_FILE"
#	if [[ $NEW_FRM -lt $RES ]]; then
#		NEW_FRM=$((RES))
#		NEW_FN=$FRM_FILE
#	fi
#done < "$INF_DIR"/frm_files.txt 
#rm "$INF_DIR"/frm_files.txt 

#if [[ $OLD_FRM -lt $NEW_FRM ]] && [[ $OLD_FRM -ne 0 ]]; then 
#	if [[ $1 == "" ]] || [[ $1 == "2" && $ACTION == "auto" ]]; then
#		/bin/systemctl stop rexgen_data.service 
#		/bin/systemctl disable rexgen_data.service
#		/home/root/rexusb/rexgen reflash "$FRM_DIR"/"$NEW_FN"
#	fi

#	if [[ $1 == "1" ]] && [[ $ACTION == "ask" ]]; then
#		echo -e "\e[32;1mInfo:\e[0m \e[32m New version $NEW_FN detected. \e[0m"
#		echo -e "\e[32m	  Start /opt/influx/check_firmware_version.sh script to apply it. \e[0m"
#		echo ""	
#	fi
#fi

#if [[ $OLD_FRM -ge $NEW_FRM ]] &&  [[ $1 == "" ]]; then
#	echo "Not detected new firmware. "
#fi
