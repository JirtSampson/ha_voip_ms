# VoIP.ms Voicemail Home Assistant Addon

Monitor your VoIP.ms voicemail from Home Assistant.

## Features

- Monitors VoIP.ms voicemail via their REST API
- Exposes voicemail counts as Home Assistant sensors via MQTT Discovery
- Provides message metadata (caller ID, date, duration, listened status)
- Streams voicemail audio for playback on Home Assistant media players

## Installation

1. Add this repository to your Home Assistant addon store
2. Install the "VoIP.ms Voicemail" addon
3. Configure with your VoIP.ms credentials
4. Start the addon

## Requirements

- VoIP.ms account with API access enabled
- Mosquitto MQTT broker addon (or external MQTT broker)

## Quick Start

1. Enable API access in your VoIP.ms account (Main Menu > SOAP and REST/JSON API)
2. Install and start the Mosquitto broker addon
3. Configure the addon with your credentials:
   - VoIP.ms username (email)
   - VoIP.ms API password
   - MQTT broker settings
4. Start the addon
5. Check for `sensor.voipms_voicemail_*` entities

## Documentation

See [DOCS.md](DOCS.md) for full documentation.

## License

MIT
