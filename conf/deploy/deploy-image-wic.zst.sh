#!/bin/bash
# Script for deploy
# copy needed files 

CURR_DIR=$PWD
if [[ ! -d $CURR_DIR ]]; then
    echo "Folder $CURR_DIR not exists."
    exit
fi

MACHINE=$(sudo cat $CURR_DIR/conf/local.conf | grep 'MACHINE' | sed "s/'//g" | sed "s/ //g" | awk -F '??=' '{print $2}')

TMP_DIR=$CURR_DIR"/tmp/deploy/images/""$MACHINE"
UUU_DIR=$PWD"/uuu-deploy/"
UUU_FILES_DIR=$PWD"/uuu-deploy/files/"
if [[ ! -d $UUU_FILES_DIR ]]; then
    mkdir -p $UUU_FILES_DIR
    cp ../sources/meta-influx/conf/deploy/deploy-image-wic.uuu $UUU_DIR/
    cp ../sources/meta-influx/conf/deploy/uuu* $UUU_DIR/
fi

#echo "Copying deploying files ..."
cp "$TMP_DIR"/imx-boot-"$MACHINE"-sd.bin-flash_evk "$UUU_FILES_DIR"/imx-boot-redge-sd.bin
cp "$TMP_DIR"/imx8mm-influx-rex-smart_v2.dtb "$UUU_FILES_DIR"/
#cp "$TMP_DIR"/imx8mm-influx-rex-smart_v2-1mw.dtb "$UUU_FILES_DIR"/

ZST_FILE=$(ls -d $(ls -t "$TMP_DIR"/*.rootfs.wic.zst | head -1))
if [ -v $ZST_FILES ]; then
    cp $ZST_FILE "$UUU_FILES_DIR"
    zstd -d $UUU_FILES_DIR/*.rootfs.wic.zst
    mv $UUU_FILES_DIR/*.rootfs.wic $UUU_FILES_DIR/"$MACHINE".wic
    rm $UUU_FILES_DIR/*.rootfs.wic.zst
fi

# uncomment this when using local machine for build
#echo "Deploying ..."
#sudo "$UUU_DIR"/uuu "$UUU_DIR"deploy-image-wic.uuu

# uncomment this when using remote machine for build
echo "Archiving ..."
tar czf uuu-deploy.tgz uuu-deploy/
