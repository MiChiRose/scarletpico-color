# Battery voltage monitor — current GP29-only hardware

Update, 2026-10-20: user confirmed the previous 2.2.2 SHADOW FAST works with
the same assembled circuit. Both new native 2.2.5/LCD12 builds fail to display
the menu correctly. Do not infer a faulty capacitor from that software change.
The current **2.2.6 LEGACY222** candidate adds the indicator to the exact
hardware-working 2.2.2 binary, preserving its driver/clock/356x320 rendering.
Menu indicator x400…479, game indicator x418…479. Only GP29; default ON;
no battery settings extension or charger-status inputs. Hardware ADC accuracy
and physical acceptance of this added code still require checking.
See [2.2.6 instructions](../firmware/releases/2026-10-20-rp2040-legacy222-battery/README-RU.md).

The following 2.2.5 software details describe the superseded native test,
not the current 2.2.6 implementation. The divider/power wiring is unchanged.

User confirmed assembly on 2026-10-20. Only GP29 is free/accessibly wired;
GP18/19 are NOT connected. Current firmware never initialises/reads them.
Two equal resistors marked 472 are **4.7 kΩ**, giving the same 2:1 ratio as
the older proposed 47 kΩ pair. The ADC node has a parallel ceramic filter to
system ground (target 100 nF…1 µF; salvaged part's capacitance not verified).

The revised wiring switches **protected OUT+ before the boost converter**.
The divider's upper resistor takes this switched positive, not permanent B+
or boosted 5 V. Lower resistor goes to protected OUT− / system GND. Assumes
a non-isolated common-ground boost. This avoids the boost LED running while
off and disconnects the sense source with the console. Never bypass protection
by joining B− to OUT−. External MCU USB can introduce other power paths;
disconnect battery/external console supply when flashing.

Firmware defaults ON for this assembled circuit (new BAT2 settings extension;
valid BAT2 OFF is respected, old BAT1 state is not migrated). Icon and voltage
are at top right in menu and game, all within x=400…479 / y=0…43; the game
ends at x=399. ADC 16-sample average every second, smoothing, nominal 3.3 V
reference; bands are approximate voltage bands, not capacity percentages.
No charging/complete indicator is possible from these connections alone.
Invalid 2.50–4.35 V range readings display `--.--V`; a stable low reading
changes the indicator colour. No automatic cutoff, no physical ADC validation.

See [current release instructions](../firmware/releases/2026-10-20-rp2040-gp29/README-RU.md).
The following section is historical 2.2.4 interface research, NOT the current
assembled wiring or current firmware behaviour.

---

## Historical battery and TP4056 monitor — 2.2.4 proposal

This is the electrical interface expected by firmware 2.2.4, not approval to
solder raw charger signals to the RP2040. Hardware has not been tested.

## Confirmed current power path

User confirmation on 2026-10-20:

- Cell connects to TP4056 B+ / B−.
- TP4056 OUT+ / OUT− feed a boost converter.
- Boost converter 5 V feeds RP2040 5V/GND.
- Power switch is between boost converter 5 V and RP2040, not before the boost.
- User reports six switch terminals with pairs paralleled. Whether these are
  external wiring bridges or internal connections is not yet confirmed; do not
  assume that an independent unused pole is available. Centre contacts on a
  conventional DPDT are the commons, not a neutral/off position.

Consequently the RP2040's 5 V supply cannot measure cell state of charge.
The boost input and battery remain live when the console switch is off.
This document does not validate the charger current, battery protection,
simultaneous play/charge or the boost converter's power-path arrangement.

## Firmware interface

| RP2040 GPIO | Expected signal |
| --- | --- |
| GP29 / ADC3 | Half of protected cell voltage, nominal 47 kΩ / 47 kΩ divider |
| GP18 | Isolated charge-status output, active LOW while CHRG is asserted |
| GP19 | Isolated charge-complete output, active LOW while STDBY is asserted |

These pins are unused in the inspected native RP2040 firmware. GP18/19 are
small solder pads on RP2040-Zero-style boards; verify markings/layout on the
actual clone. Do not count physical header positions as GPIO numbers.

The ADC uses nominal 3.3 V reference and a 2:1 divider ratio. A normal 4.2 V cell
therefore produces about 2.1 V. Use 1% resistors and a nominal 100 nF filter
capacitor at ADC-to-system-ground. Calibrate against a meter before treating
the displayed hundredths of a volt as accurate.

The source must remain the protected cell side BEFORE the boost converter,
not its regulated 5 V output or any USB-fed common supply rail. Reference the
measurement to the protected output return/system ground; do not connect
B− and OUT− together and bypass the protection MOSFETs.

## Off-state isolation is required

An always-connected battery divider can feed the RP2040 ADC while the MCU is
unpowered, through the input protection structure. Software OFF is NOT an
electrical isolator. Do not install a permanently live divider as shown by
an oversimplified two-resistor sketch.

If the actual slide switch is DPDT (six pins, two independent groups), a
possible solution is its unused second pole switching the protected battery
positive into the divider while the first pole switches the existing 5 V rail.
Do not connect the two switched positive rails together. Confirm pin grouping
and continuity of the actual switch before finalising this circuit. The
divider's lower resistor keeps the ADC node discharged when disconnected.

For a three-pin single-pole switch, a separately designed power-off-safe
sense switch/buffer, or an appropriate two-pole replacement is needed. Do not
solve this by merely inserting a series resistor or relying on firmware.

## Charger LEDs / status signals

TP4056 CHRG (pin 7) and STDBY (pin 6) are open-drain outputs. On common modules
their LED/resistor networks go to the charging input, so an inactive node
can rise above 3.3 V. Never directly connect either LED pad to the MCU.

The firmware expects TWO optically isolated, active-low receiver outputs:

- Each optocoupler receiver emitter connects to RP2040 system ground.
- Its collector connects to GP18 or GP19, pulled up to the RP2040's own 3.3 V.
  Firmware also enables the GPIO's internal pull-up.
- The corresponding optocoupler input must turn on when that charger status
  is asserted. Its input resistor, LED connections and current must be
  selected after inspecting the actual TP4056 module and optocoupler ratings.
- Do not casually parallel another LED/opto LED onto the module LED or join
  charger-side ground to protected OUT−: inspect the protection topology.

This isolates both logic voltage and the powered charger from an unpowered
MCU. The existing LEDs need not be visible through the case. This is a receiver
interface specification, not a completed optocoupler input wiring diagram.

| GP18 | GP19 | Screen meaning |
| --- | --- | --- |
| HIGH | HIGH | IDLE/UNKNOWN: neither status asserted; does NOT prove USB is absent |
| LOW | HIGH | CHARGING: TP4056 reports a charge cycle |
| HIGH | LOW | CHARGE DONE: TP4056 reports termination |
| LOW | LOW | CHECK SIGNALS: conflicting inputs; not assumed to be full |

The signals do not independently prove that a battery is present. Missing
battery, temperature faults and some module implementations may blink/change
states. Firmware debounces readings; it does not replace the charging safety
controller or fix load-sharing/termination problems while gaming.

## Display behaviour

- Default is OFF until explicitly enabled under Settings → Battery / Charger.
- The confirmation screen warns about wiring. Saving happens when leaving Settings.
- Header shows five voltage bands, voltage and charge status.
- In-game left rail shows voltage, charge status and five bands without
  changing the emulated image or touching the LCD from the emulation core.
- ADC is averaged over 16 conversions once per second; displayed voltage
  is smoothed. Status is sampled no faster than 10 Hz and needs four
  consecutive equal samples. CPU load can make updates slower.
- Raw estimates outside 2.50–4.35 V show SENSOR CHECK, not a fake full/empty battery.
- Low warning requires five low samples (filtered ≤3.50 V); it clears at
  ≥3.65 V. This is an early warning, not automatic shutdown or cell protection.
- Bands use 3.50 / 3.65 / 3.75 / 3.90 / 4.05 V thresholds, a provisional
  voltage-based estimate. They are not calibrated capacity percentages,
  especially while charging or under load. CHARGE DONE does not force five bars.
- The screen only works while the console itself is on. This does not wake
  or power the screen when the physical switch is off.

## Primary references

- [TP4056 manufacturer datasheet](https://evelta.com/content/datasheets/129-TP4056-42-ESOP8.pdf)
- [RP2040 ADC and electrical limits](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [Waveshare RP2040-Zero schematic](https://files.waveshare.com/upload/4/4c/RP2040_Zero.pdf)

Still required before exact soldering instructions: switch contact continuity /
whether the parallel links are external, and close-up photos of both sides of
the actual charger module.
