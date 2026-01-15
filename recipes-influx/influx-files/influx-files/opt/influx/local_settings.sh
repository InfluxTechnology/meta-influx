#!/bin/sh

WIFI_PSK=$(/usr/bin/fw_printenv local_wifi_psk | cut -d = -f 2)
WIFI_SSID=$(/usr/bin/fw_printenv local_wifi_ssid | cut -d = -f 2)
if [[ "$WIFI_PSK" != "" && "$WIFI_SSID" != "" ]]; then
	echo ''  >> /etc/wpa_supplicant.conf
	echo 'network={' 		 >> /etc/wpa_supplicant.conf
	echo '	ssid="InfluxTech-2.4G"'  >> /etc/wpa_supplicant.conf
	echo '	psk="infl-omada-eap245"' >> /etc/wpa_supplicant.conf
	echo '}' >> /etc/wpa_supplicant.conf
	echo ''  >> /etc/wpa_supplicant.conf

	/usr/bin/fw_setenv local_wifi_psk ''
	/usr/bin/fw_setenv local_wifi_ssid ''
fi

tmp=$(mktemp)
MEND_URL=$(/usr/bin/fw_printenv local_mender_server | cut -d = -f 2)
MEND_TOKEN=$(/usr/bin/fw_printenv local_mender_token | cut -d = -f 2)
if [[ "$MEND_URL" != "" && "$MEND_TOKEN" != "" ]]; then
	jq --arg a "$MEND_URL" '.ServerURL = $a' /etc/mender/mender.conf > "$tmp" && mv "$tmp" /etc/mender/mender.conf
        jq --arg a "$MEND_TOKEN" '.TenantToken = $a' /etc/mender/mender.conf > "$tmp" && mv "$tmp" /etc/mender/mender.conf

        /usr/bin/fw_setenv local_mender_server ''
        /usr/bin/fw_setenv local_mender_token ''
fi
