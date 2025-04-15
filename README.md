# pycync_lan (cync_lan)
![GitHub Release](https://img.shields.io/github/v/release/baudneo/cync-lan) 
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/baudneo/cync-lan/container-package-publish.yml) 
![Docker Pulls](https://img.shields.io/docker/pulls/baudneo/cync-lan)

>[!IMPORTANT]
> [DNS redirection REQUIRED](./docs/DNS.md)

Async HTTP/MQTT LAN controller for Cync/C by GE devices. **Local** only control
of **most** Cync devices via MQTT JSON payloads following the Home Assistant MQTT JSON schema. 
This project masquerades as the cloud server, allowing you to control your devices locally.

**This is a work in progress, and may not work for all devices.** 
See [known devices](docs/known_devices.md) for more information. Battery powered devices are currently *not* supported due to them being BTLE only.

Forked from [cync-lan](https://github.com/iburistu/cync-lan) and 
[cync2mqtt](https://github.com/juanboro/cync2mqtt) - All credit to 
[iburistu](https://github.com/iburistu) and 
[juanboro](https://github.com/juanboro)

## Prerequisites
- Python 3.8+ (Walrus [:=] operator used)
- A minimum of 1, non battery powered, Wi-Fi (*Direct Connect*) Cync / C by GE device to act as the TCP <-> BT bridge (always on)
- Cync account with devices added
- MQTT broker (I recommend EMQX)
- [Export devices](./docs/command_line_sub_commands.md#export) from the Cync cloud to a YAML file; first export requires account email, password and an OTP emailed to you
- [DNS override/redirection](./docs/DNS.md) for `cm.gelighting.com` or `cm-ge.xlink.cn` to a local host that will run `cync-lan`
- **Non Docker:** [Create self-signed SSL certs](./docs/install.md#setup) using `CN=*.xlink.cn` for the server. You can use the `create_certs.sh` script
- **Optional:** *[Firewall](#firewall) rules to allow cync devices to talk to `cync-lan`* **(VLANs?)**

>[!NOTE]
> You still need to use your Cync account to add new devices as you acquire them.
 
## Installation
>[!IMPORTANT]
> You must create a virtualenv and download the cync-lan.py script in order to export 
> your Cync devices from the Cync cloud API. Even if you only plan on using a docker set-up.
> This requires your email, password and the code that will be emailed to you during export.

You will want to save the virtualenv setup for future use. If you add new devices to your 
Cync account, you need to export the config. Please see [Install docs](./docs/install.md) for more information.

### Updating Docker Container
#### Updating using a new image
- `cd` to cync-lan docker directory where `docker-compose.yaml` is located
- run: `docker compose pull && docker compose up -d --force-recreate`
#### 'Upgrade in-place'
If you want to update the container in-place, you can:
- `cd` to cync-lan docker directory where `docker-compose.yaml` is located
- `wget 'https://raw.githubusercontent.com/baudneo/cync-lan/refs/heads/python/src/cync-lan.py'`
- edit `docker-compose.yaml` and uncomment the bind mount line in volumes for ./cync-lan.py
    - ```
      volumes:
        # Create a ./config dir and place the exported config file in this directory
        - ./config:/root/cync-lan/config
        # Want to run custom code or upgrade in place? Bind-mount the custom/upgraded cync-lan.py into the container!
        #- ./cync-lan.py:/root/cync-lan/cync-lan.py  <---- uncomment this line
      ```
- `docker compose up -d --force-recreate` to finalize the upgrade in place.

## Re-routing / Overriding DNS
>[!WARNING] 
> After freshly redirecting DNS: Devices that are currently
> talking to the Cync cloud will need to be power cycled before they make
> a DNS request and connect to the local `cync-lan` server.

There are detailed instructions for OPNSense and Pi-hole. 
See [DNS docs](docs/DNS.md) for more information.

## Tips
See [Tips](docs/tips.md) for more information on how to get the most out of this project.

## Config file
See the example [config file](./cync_mesh_example.yaml)

### Export config from Cync cloud API
There is an `export` [sub command](./docs/command_line_sub_commands.md#export) 
that will query the Cync cloud API and export all homes and each homes devices to a YAML file.

## CLI arguments
You can always supply `--help` to the cync-lan.py script to get a 
breakdown. Please see the 
[sub-command docs](./docs/command_line_sub_commands.md) for more information.

## Env Vars
> [!NOTE]
> The `CYNC_MQTT_URL` variable is **deprecated** and will be removed in a future release.
> For now, it will be parsed into `CYNC_MQTT_HOST`, `CYNC_MQTT_PORT`, `CYNC_MQTT_USER`, and `CYNC_MQTT_PASS`.

| Variable                 | Description                                       | Default               |
|--------------------------|---------------------------------------------------|-----------------------|
| `CYNC_MQTT_HOST`         | Host of MQTT broker                               | `homeassistant.local` |
| `CYNC_MQTT_PORT`         | Port of MQTT broker                               | `1883`                |
| `CYNC_MQTT_USER`         | Username for MQTT broker                          |                       |
| `CYNC_MQTT_PASS`         | Password for MQTT broker                          |                       |
| `CYNC_MQTT_CONN_DELAY`   | Delay between MQTT re-connections (seconds)       | `10`                  |
| `CYNC_DEBUG`             | Enable debug logging                              | `0`                   |
| `CYNC_RAW_DEBUG`         | Enable raw binary message debug logging           | `0`                   |
| `CYNC_CERT`              | Path to cert file                                 | `certs/server.pem`    |
| `CYNC_KEY`               | Path to key file                                  | `certs/server.key`    |
| `CYNC_PORT`              | Port to listen on (shouldn't need to change)      | `23779`               |
| `CYNC_HOST`              | Interface to listen on                            | `0.0.0.0`             |
| `CYNC_TOPIC`             | MQTT topic                                        | `cync_lan`            |
| `CYNC_HASS_TOPIC`        | Home Assistant topic                              | `homeassistant`       |
| `CYNC_HASS_STATUS_TOPIC` | HASS status topic for birth / will                | `status`              |
| `CYNC_HASS_BIRTH_MSG`    | HASS birth message                                | `online`              |
| `CYNC_HASS_WILL_MSG`     | HASS will message                                 | `offline`             |
| `CYNC_CMD_BROADCASTS`    | Number of WiFi devices to send state commands to  | `2`                   |
| `CYNC_MAX_TCP_CONN`      | Maximum Wifi devices allowed to connect at a time | `8`                   |
| `CYNC_TCP_WHITELIST`     | Comma separated string of allowed IPs             | Allow ALL IPs         |


## Controlling devices
Devices are controlled by JSON MQTT messages. This was designed to be used 
with Home Assistant, but you can use any MQTT client to send messages 
to the MQTT broker.

**Please see [Home Assistant MQTT documentation](https://www.home-assistant.io/integrations/light.mqtt/#json-schema) 
for more information on JSON payloads.** This repo will try to stay up to
date with the latest Home Assistant MQTT JSON schema.

## Home Assistant
This script uses the MQTT discovery mechanism in Home Assistant to 
automatically add devices. You can control the Home Assistant MQTT 
topic via the environment variable `CYNC_HASS_TOPIC` (default: `homeassistant`).

## Debugging / socat
If your devices are not responding to commands, it's likely that the TCP
communication on the device is different. You can either open an issue 
and I can walk you through getting good debug logs, or you can use 
`socat` to inspect (MITM) the traffic of the device communicating with the 
cloud server in real-time yourself by running:

```bash
# make sure to create the self-signed certs first
# Older firmware devices
socat -d -d -lf /dev/stdout -x -v 2> dump.txt ssl-l:23779,reuseaddr,fork,cert=certs/server.pem,verify=0 openssl:34.73.130.191:23779,verify=0
# Newer firmware devices (Notice the last IP change)
sudo socat -d -d -lf /dev/stdout -x -v 2> dump.txt ssl-l:23779,reuseaddr,fork,cert=certs/server.pem,verify=0 openssl:35.196.85.236:23779,verify=0
```
In `dump.txt` you will see the back-and-forth communication between the device and the cloud server.
`>` is device to server, `<` is server to device.

# Firewall
Once the devices are local, they must be able to initiate a connection to 
the `cync-lan` server. If you block them from the internet, don't forget to 
allow them to connect to the `cync-lan` server.

## OPNsense Example
Please see the [example](./docs/troubleshooting.md#opnsense-firewall-example)
in the troubleshooting docs.

# Power cycle devices after DNS re-route
Devices make a DNS query on first startup (or after a network loss,
like AP reboot) - you need to power cycle all devices that are currently 
connected to the Cync cloud servers before they request a new DNS record 
and will connect to the local `cync-lan` server.

# Troubleshooting
If you are having issues, please see the 
[Troubleshooting docs](docs/troubleshooting.md) for more information.

# Buy devices to be supported
If you really want a device added, [purchase it from this Amazon wish list](https://www.amazon.ca/registries/gl/guest-view/270SHDZQLXRU8), 
and it will be sent to me. I will add support ASAP.

