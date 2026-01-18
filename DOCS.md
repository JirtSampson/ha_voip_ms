# VoIP.ms Voicemail Home Assistant Addon

This addon monitors your VoIP.ms voicemail and exposes it to Home Assistant via MQTT Discovery.

## Features

- Automatic discovery of voicemail mailboxes
- Real-time voicemail count sensors
- Message metadata (caller ID, date, duration, etc.)
- Audio playback through Home Assistant media players
- Configurable polling interval

## Prerequisites

1. **VoIP.ms Account** with voicemail enabled
2. **VoIP.ms API Access** enabled in your account
3. **Mosquitto MQTT Broker** addon installed and configured

### Enabling VoIP.ms API Access

1. Log in to your VoIP.ms account
2. Navigate to **Main Menu > SOAP and REST/JSON API**
3. Set "API Enabled" to **Yes**
4. Set an **API Password** (this is different from your account password)
5. Note your account email and API password for configuration

## Configuration

### Required Settings

| Option | Description |
|--------|-------------|
| `voipms_username` | Your VoIP.ms account email |
| `voipms_api_password` | API password from VoIP.ms portal |

### Optional Settings

| Option | Default | Description |
|--------|---------|-------------|
| `mailboxes` | Empty (all) | List of specific mailbox IDs to monitor |
| `poll_interval` | 60 | Seconds between API polls (30-3600) |
| `mqtt_host` | core-mosquitto | MQTT broker hostname |
| `mqtt_port` | 1883 | MQTT broker port |
| `mqtt_username` | Empty | MQTT username |
| `mqtt_password` | Empty | MQTT password |
| `audio_port` | 8099 | Port for audio streaming server |

### Example Configuration

```yaml
voipms_username: "your-email@example.com"
voipms_api_password: "your-api-password"
mailboxes:
  - "12345"
  - "67890"
poll_interval: 60
mqtt_host: "core-mosquitto"
mqtt_port: 1883
mqtt_username: "mqtt-user"
mqtt_password: "mqtt-password"
audio_port: 8099
```

## Entities Created

For each mailbox, a sensor entity is created:

- **Entity ID**: `sensor.voipms_voicemail_{mailbox_id}`
- **State**: Number of new (unlistened) messages
- **Attributes**:
  - `total_messages`: Total messages in mailbox
  - `new_messages`: Number of unlistened messages
  - `messages`: List of message objects

### Message Object Attributes

Each message in the `messages` attribute contains:

| Attribute | Description |
|-----------|-------------|
| `message_num` | Message number |
| `folder` | Folder name (INBOX, Old, etc.) |
| `callerid` | Caller ID |
| `date` | Message date/time |
| `duration` | Duration in seconds |
| `listened` | "yes" or "no" |
| `urgent` | "yes" or "no" |
| `audio_url` | URL to stream the audio file |

## Example Automations

### Notify on New Voicemail

```yaml
automation:
  - alias: "New Voicemail Notification"
    trigger:
      - platform: state
        entity_id: sensor.voipms_voicemail_12345
    condition:
      - condition: template
        value_template: >
          {{ trigger.to_state.state | int > trigger.from_state.state | int }}
    action:
      - service: notify.mobile_app_phone
        data:
          title: "New Voicemail"
          message: >
            From: {{ state_attr('sensor.voipms_voicemail_12345', 'messages')[0].callerid }}
            Duration: {{ state_attr('sensor.voipms_voicemail_12345', 'messages')[0].duration }}s
```

### Play Voicemail on Speaker

```yaml
script:
  play_latest_voicemail:
    alias: "Play Latest Voicemail"
    sequence:
      - service: media_player.play_media
        target:
          entity_id: media_player.living_room_speaker
        data:
          media_content_id: >
            {{ state_attr('sensor.voipms_voicemail_12345', 'messages')[0].audio_url }}
          media_content_type: audio/wav
```

### Dashboard Card

```yaml
type: entities
title: Voicemail
entities:
  - entity: sensor.voipms_voicemail_12345
    name: Mailbox 12345
  - type: attribute
    entity: sensor.voipms_voicemail_12345
    attribute: total_messages
    name: Total Messages
```

## Troubleshooting

### API Connection Errors

- Verify your VoIP.ms username and API password
- Ensure API access is enabled in your VoIP.ms account
- Check that your IP is not blocked by VoIP.ms

### MQTT Connection Errors

- Verify Mosquitto addon is running
- Check MQTT credentials if authentication is enabled
- Ensure `mqtt_host` is correct (use `core-mosquitto` for the HA addon)

### No Entities Appearing

- Check addon logs for errors
- Verify MQTT broker is receiving messages
- Ensure you have voicemail mailboxes configured in VoIP.ms

### Audio Playback Issues

- Verify port 8099 is accessible
- Check that your media player supports WAV audio
- Review addon logs for audio server errors

## Support

For issues and feature requests, please visit the GitHub repository.
