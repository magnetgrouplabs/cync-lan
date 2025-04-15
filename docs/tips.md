# Command latency and device state sync
- Command latency mens: how long it takes for a MQTT state change command to be issued and for the physical device to change state.
- Device state sync means: HASS light group of 9 issuing `off`. How in-sync the devices are when changing state, one after the other or in parallel?
## Fine-tuning
There seems to be some fine-tuning that can be done using `CYNC_MAX_TCP_CONN` and `CYNC_CMD_BROADCASTS` env vars.
- `CYNC_MAX_TCP_CONN` is the maximum number of TCP devices connected to cync-lan at a time. This is set to 8 by default.
  - I've had a decent experience with 4-6 devices connected at a time and 3-5 commands broadcast.
- If you only have 1-3 WiFi devices connected you will notice a delay in the command being sent to the device and sequential state changes.

>[!NOTE]
> It may also be the way HASS issues commands in a light group. I also notice slow / not in-sync responses with ZigBee lights as well

# Some devices are better at being TCP <-> BTLE 'bridges'

1. LED strip controllers are the best bridges
2. Bulbs, possibly down light / wafer / under cabinet lights as well
3. Switches are untested
4. Indoor plugs are ok (outdoor untested)
5. thermostat untested

## Use `CYNC_TCP_WHITELIST` to limit access to the cync-lan server
- This is a comma separated list of IPs that are allowed to connect to the cync-lan server
  - By default, all IPs are allowed to connect
- This allows you to choose certain devices to connect to cync-lan (and also limit how many devices)
  - Set the IPs of always on devices and prefer the better 'bridges'
  - Example: `CYNC_TCP_WHITELIST: '10.0.2.20, 10.0.2.24, 10.0.2.29, 10.0.2.30, 10.0.2.33'`
  - This will allow only those IPs to connect to the cync-lan server, which also only allows a max of 5 devices
  - Now try fine-tuning `CYNC_CMD_BROADCASTS` to see if you can get better performance (also try increasing / decreasing connected devices)

# Motion + Ambient light switch data
Unfortunately, the motion and ambient light data is not available in the Cync cloud API or to cync-lan. I recommend using the Cync app support option and requesting that they expose the motion and ambient light via the cloud, then for sure we can read it.

>[!IMPORTANT]
> **Do not** mention this project to them, just say you would like it exposed to google home / alexa and the cync app