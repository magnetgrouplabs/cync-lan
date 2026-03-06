---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

**How are you running CyncLAN?**
[ ] HASS app
[ ] Docker

>[!IMPORTANT]
> Please enable DEBUG level logs and catch the error
> HASS app configuration: debug level toggle ON
> Docker image: CYNC_DEBUG=yes in the env vars

**What version**
In the logs, there will be a version number right after starting, or you can exec into the docker container and run `cync-lan -V`

```
03/06/26 14:41:22.475 INFO [main:194] > main: App config has set logging level to: Debug
03/06/26 14:41:22.476 INFO [utils:307] > check_uuid: UUID found in /homeassistant/.storage/cync-lan/config/uuid.txt for the 'CyncLAN Bridge' MQTT device
03/06/26 14:41:22.476 INFO [main:85] > CyncLAN:init: CyncLAN (version: 0.0.4b1) stack initializing...
```


**Describe the bug**
A clear and concise description of what the bug is.

**Logs**
Please add logs here:

```log


```

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Additional context**
Add any other context about the problem here.
