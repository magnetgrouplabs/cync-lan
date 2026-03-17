Devices known to work, kind of work, and known not to work are listed here.

# Known Good
- Cync: Direct connect **bulbs** (Full color, Decorative [edison], white temp, dimmable)
    - Direct connect products are Wi-Fi and Bluetooth LE using a realtek chip (RTL8010, RTL8020CM)
- Cync/C by GE: Bluetooth LE only bulbs \**needs at least 1 Wi-Fi device to act as a TCP<->BT bridge*
    - C by GE BT only: These are telink based devices 
- Cync: Indoor smart plug
    - Outdoor plug (dual outlet)
- Cync: Wired switches (on/off, dimmer, white temp control) [motion/ambient light data is not exposed, switch uses it internally]
- Cync: Full color LED light strip [responds slightly differently than other devices]
    - Outdoor light strip should also work, currently unconfirmed
- Cync undercabinet lights
- Cync wafer / down lights

# Known Bad
- Basically anything with a battery as its power source. They are BTLE only and are not supported by cync-lan **yet**.
    - Wire free switch OR dimmer [white temp control].
    - Sensors [motion, temperature/humidity, etc.].
      - Temp/Hum sensors bound to the thermostat may be exposed (unconfirmed). 

# Work In Progress
- Fan controller (logic has been added, need testers)

# Future devices
- Dynamic lights (Sound/Music sync, segmented leds) 
- Thermostat 
  - I've seen the device details from the cloud, but have not seen any binary data. CyncLAN may recognize the \
thermostat and export it to the config, but it has no idea how to communicate with it **yet**