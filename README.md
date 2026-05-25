# Telescope Handcontroller Replacement

Replace your Sky-Watcher SynScan handcontroller with a Raspberry Pi 4-based
autonomous controller featuring touchscreen control, camera support, and
automated plate-solving alignment.

## Hardware

| Component | Model | Connection |
|-----------|-------|------------|
| Raspberry Pi | Pi 4 (4GB) | — |
| Mount | Sky-Watcher EQ3-2 + SynScan | RJ45 -> EQDIR USB -> Pi |
| Guide scope cam | ZWO ASI120MC | USB -> Pi |
| Imager | ZWO ASI715MC | USB -> Pi |
| Display | 10" HDMI touchscreen | HDMI + USB (touch) -> Pi |

## Hardware Wiring

### Mount Connection (EQDIR)

```
EQ3-2 Mount RJ45 port  <--RJ45 cable-->  EQDIR module  <--USB-->  Raspberry Pi
```

The EQDIR cable replaces the SynScan handcontroller. It connects the mount's
RJ45 motor control port directly to USB. No handcontroller needed.

**DO NOT** connect both the handcontroller and EQDIR simultaneously.

### Camera Connections

Both ZWO cameras connect via USB directly to the Pi. A powered USB hub is
recommended for stable operation.

## Software Stack

- **OS**: Raspberry Pi OS (64-bit) Bookworm
- **Device Control**: INDI (EQMOD + ASI drivers)
- **Plate Solving**: ASTAP (offline) / Astrometry.net (online)
- **UI**: Python + PyQt5
- **Alignment**: Traditional 1/2/3 star + automated plate-solving

## Quick Install

```bash
git clone <repo-url> ~/telescope
cd ~/telescope
chmod +x setup.sh
./setup.sh
```

## Manual Start

```bash
cd ~/telescope
python3 src/main.py
```

## Usage

### Mount Tab
- **Direction Pad**: N/S/E/W buttons (press & hold for motion, release to stop)
- **Speed**: Guide / Centering / Finding / Max
- **Track ON/OFF**: Toggle sidereal tracking
- **Park/Unpark**: Park mount at home position

### GOTO Tab
- Enter RA/DEC coordinates manually
- Browse object catalog (Messier, NGC, planets)
- Search objects by name or constellation
- Selected objects show visibility

### Align Tab
- **Traditional**: 1-star, 2-star, or 3-star alignment
- **Plate Solve**: Automated camera-based alignment
  1. Slew near a known star
  2. Camera captures image
  3. ASTAP solves the field
  4. Mount syncs to solved coordinates
  5. Repeat for improved accuracy
- **Sync**: Force sync at current position

### Camera Tab
- Control exposure time and gain
- Capture and preview images
- Separate controls for guider and imager

## Plate Solving

### Offline (ASTAP, recommended)
```bash
# Install ASTAP with Gaia star database
# Configure path in config/telescope_config.json
```

### Online (Astrometry.net)
Set `"method": "online"` in config and optionally provide an API key.

## Alignment Flow

1. **Level and polar align** the mount physically
2. Power on, connect everything
3. Start the app: `python3 src/main.py`
4. **Align tab** -> choose method:
   - **1-Star**: Quick, less accurate
   - **2-Star**: Good balance
   - **3-Star**: Most accurate traditional
   - **Plate Solve**: Fully automated, most accurate
5. After alignment, use GOTO for any object

## Configuration

Edit `config/telescope_config.json`:
- Site latitude/longitude
- Camera settings (gain, offset, temperature)
- Plate solver settings
- UI theme and layout

## Troubleshooting

| Problem | Check |
|---------|-------|
| Mount not detected | EQDIR cable connected? `ls /dev/ttyUSB*` |
| Camera not found | USB connection? `lsusb` should show ZWO |
| Plate solve fails | ASTAP installed? Star database present? |
| Touch not working | Check touch USB cable |
| INDI server fails | `indiserver -v indi_eqmod_telescope` to test |

Logs: `/tmp/telescope_controller.log`

## License

MIT
