#!/bin/sh

#if [ ! -f /data/mender/mender_artifact ]; then
#        exit 1
#fi

if [ -d /opt/influx/releases/ ]; then
        chown -hR root:root /opt/influx/releases/
fi

ARTIFACT=$(cat /data/mender/mender_artifact)
#read -ra ARR1 <<< $ARTIFACT
#ARTIFACT1=${ARR1[1]}
ARTIFACT1="${ARTIFACT1//[!1234567890.]/}"
ARTIFACT1=$(echo "$ARTIFACT1" | sed 's/^.//')
if [[ "$ARTIFACT1" == "" ]]; then
        ARTIFACT1="0"
fi
NUMBER1=$(echo "$ARTIFACT1" | tr -dc '0-9')

ARTIFACT=$(mender-update show-artifact)
#read -ra ARR2 <<< $ARTIFACT
#ARTIFACT2=${ARR2[1]}
ARTIFACT2="${ARTIFACT//[!1234567890.]/}"
ARTIFACT2=$(echo "$ARTIFACT2" | sed 's/^.//')
NUMBER2=$(echo "$ARTIFACT2" | tr -dc '0-9')

SETUP_FILE=/opt/influx/releases/"$ARTIFACT2"/setup.sh
RELEASE_DIR=/opt/influx/releases/"$ARTIFACT2"
REBOOT_FILE=/opt/influx/reboot.sh

if [ -f "$REBOOT_FILE" ]; then
    rm "$REBOOT_FILE"
fi

if [[ $NUMBER1 -lt $NUMBER2 ]]; then
        if [ ! -f "$SETUP_FILE" ]; then
                exit 1
        fi

        # check and apply previously releases
        ls "$RELEASE_DIR"/*.tgz > /opt/influx/releases.txt
        while read RELEASE; do
                RELEASE_NAME=$(basename -- "$RELEASE")
                RELEASE_NAME="${RELEASE_NAME%.*}"

                if [[ "$ARTIFACT1" < "$RELEASE_NAME" ]]; then
                        tar xzf "$RELEASE" -C "$RELEASE_DIR"
                        chown -hR root:root "$RELEASE_DIR"/"$RELEASE_NAME"

                        "$RELEASE_DIR"/"$RELEASE_NAME"/setup.sh "$RELEASE_DIR"/"$RELEASE_NAME"
                        rm -fr "$RELEASE_DIR"/"$RELEASE_NAME"
                fi

        done < /opt/influx/releases.txt

        sh "$SETUP_FILE"
        rm /data/mender/mender_artifact
        rm /opt/influx/releases.txt

        /usr/bin/crontab -u root -l |  /bin/grep -v "* /opt/influx/release_check.sh" |  /usr/bin/crontab -
        if [ -f "$REBOOT_FILE" ]; then
                /usr/bin/crontab -u root -l | { cat; echo "*/2 * * * * /opt/influx/reboot.sh"; } | /usr/bin/crontab -
        fi
fi

echo "pro-"$NUMBER2 > /etc/hostname

