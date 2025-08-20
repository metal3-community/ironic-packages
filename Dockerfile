FROM docker.io/chainguard/python:latest-dev AS builder

ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/var/lib/openstack/ironic/bin:$PATH"

USER root

WORKDIR /var/lib/openstack

RUN python -m venv /var/lib/openstack/ironic
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM docker.io/chainguard/python:latest-dev

WORKDIR /var/lib/openstack

ENV PYTHONUNBUFFERED=1
ENV PATH="/var/lib/openstack/ironic/bin:$PATH"
ENV IRONIC_THREAD_STACK_SIZE=0

USER root
COPY ironic_server.py /var/lib/openstack/ironic_server.py
COPY --from=builder --link /var/lib/openstack/ironic /var/lib/openstack/ironic

ENV OS_AUTH_STRATEGY="noauth"
ENV OS_DEBUG="true"
ENV OS_DEFAULT_DEPLOY_INTERFACE="direct"
ENV OS_DEFAULT_INSPECT_INTERFACE="agent"
ENV OS_DEFAULT_NETWORK_INTERFACE="noop"
ENV OS_ENABLED_BIOS_INTERFACES="no-bios,redfish,idrac-redfish,irmc,ilo"
ENV OS_ENABLED_BOOT_INTERFACES="ipxe,ilo-ipxe,pxe,ilo-pxe,fake,redfish-virtual-media,idrac-redfish-virtual-media,ilo-virtual-media,redfish-https"
ENV OS_ENABLED_DEPLOY_INTERFACES="direct,fake,ramdisk,custom-agent"
ENV OS_ENABLED_FIRMWARE_INTERFACES="no-firmware,fake,redfish"
ENV OS_ENABLED_HARDWARE_TYPES="ipmi,idrac,irmc,fake-hardware,redfish,manual-management,ilo,ilo5"
ENV OS_ENABLED_INSPECT_INTERFACES="agent,irmc,fake,redfish,ilo"
ENV OS_ENABLED_MANAGEMENT_INTERFACES="ipmitool,irmc,fake,redfish,idrac-redfish,ilo,ilo5,noop"
ENV OS_ENABLED_NETWORK_INTERFACES="noop"
ENV OS_ENABLED_POWER_INTERFACES="ipmitool,irmc,fake,redfish,idrac-redfish,ilo"
ENV OS_ENABLED_RAID_INTERFACES="no-raid,irmc,agent,fake,redfish,idrac-redfish,ilo5"
ENV OS_ENABLED_VENDOR_INTERFACES="no-vendor,ipmitool,idrac-redfish,redfish,ilo,fake"
ENV OS_RPC_TRANSPORT="none"
ENV OS_USE_STDERR="true"
ENV OS_HASH_RING_ALGORITHM="sha256"
ENV OS_MY_IP="0.0.0.0"
ENV OS_WEBSERVER_VERIFY_CA="false"
ENV OS_ISOLINUX_BIN="/usr/share/syslinux/isolinux.bin"
ENV OS_GRUB_CONFIG_PATH="EFI/centos/grub.cfg"
ENV OS_AGENT_DEPLOY_LOGS_COLLECT="always"
ENV OS_AGENT_DEPLOY_LOGS_LOCAL_PATH="/shared/log/ironic/deploy"
ENV OS_AGENT_MAX_COMMAND_ATTEMPTS="30"
ENV OS_API_HOST_IP="::"
ENV OS_API_PORT="6385"

ENTRYPOINT [ "python", "/var/lib/openstack/ironic_server.py" ]