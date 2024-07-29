#!/bin/bash
# Script for deploy
# copy needed files 

CURR_DIR=$PWD
if [[ ! -d $CURR_DIR ]]; then
    echo "Folder $CURR_DIR not exists."
    exit
fi

BUILD="redge-image-base"
MACHINE=$(sudo cat $CURR_DIR/conf/local.conf | grep 'MACHINE' | sed "s/'//g" | sed "s/ //g" | awk -F '??=' '{print $2}')

TMP_DIR=$CURR_DIR"/tmp/deploy/images/""$MACHINE"
UUU_DIR=$PWD"/uuu-deploy/"
UUU_FILES_DIR=$PWD"/uuu-deploy/files/"
if [[ ! -d $UUU_FILES_DIR ]]; then
    mkdir -p $UUU_FILES_DIR
    cp ../sources/meta-influx/conf/deploy/deploy-image-wic.uuu $UUU_DIR/
    cp ../sources/meta-influx/conf/deploy/uuu $UUU_DIR/
fi

#echo "Copying deploying files ..."

cp "$TMP_DIR"/imx-boot-"$MACHINE"-sd.bin-flash_evk "$UUU_FILES_DIR"/imx-boot-redge-sd.bin
cp "$TMP_DIR"/imx8mm-influx-redge-1mw.dtb "$UUU_FILES_DIR"/
#cp "$TMP_DIR"/imx8mm-ea-ucom-kit_v2-1mw.dtb "$UUU_FILES_DIR"/

#if [ "$WIC_FLAG" = true ]; 
#then
    if [ -f $TMP_DIR/"$BUILD"-"$MACHINE"".wic.bz2" ]; then
        echo "Unpacking the wic file ..."	
    else
        echo "The wic file not exists."	
        exit;
    fi	

    if [ -f "$UUU_FILES_DIR"/"$BUILD"-"$MACHINE".wic ]; then
        rm "$UUU_FILES_DIR"/"$BUILD"-"$MACHINE".wic
    fi

    cp "$TMP_DIR"/"$BUILD"-"$MACHINE".wic.bz2 "$UUU_FILES_DIR"
    bunzip2 -d -k "$UUU_FILES_DIR"/"$BUILD"-"$MACHINE".wic.bz2 
    rm "$UUU_FILES_DIR"/"$BUILD"-"$MACHINE".wic.bz2    
#fi

# uncomment this when using local machine for build
#echo "Deploying ..."
#sudo "$UUU_DIR"/uuu "$UUU_DIR"deploy-image-wic.uuu

# uncomment this when using remote machine for build
echo "Archiving ..."
tar czf uuu-deploy.tgz uuu-deploy/
