# Copyright (C) 2025 Influx Technology

DESCRIPTION = "Create RexGen needed folders"

require inf-common.inc

# these folders will be created
NET_SERV_VER = "netservices"
INF_DIRS += " \
    ${INFLUX_DIR}${NET_SERV_VER}/bin/ \
    ${INFLUX_DIR}${NET_SERV_VER}/lib/dashboard/ \
    ${INFLUX_DIR}${NET_SERV_VER}/lib/modules/rexgen_live/ \
    ${INFLUX_DIR}${NET_SERV_VER}/lib/modules/rexgen_topology/ \
    ${INFLUX_DIR}${NET_SERV_VER}/lib/services/ \
    ${INFLUX_DIR}${NET_SERV_VER}/licensing/closed-source/ \
    ${INFLUX_DIR}${NET_SERV_VER}/licensing/open-source/ \
    ${INFLUX_DIR}${NET_SERV_VER}/scripts/ \
    ${INFLUX_DIR}${NET_SERV_VER}/services/ \
    ${INFLUX_DIR}${NET_SERV_VER}/ssl \
    ${INFLUX_DIR}${NET_SERV_VER}/systemd \
    /data/rexgen/seedkey/ \
"

