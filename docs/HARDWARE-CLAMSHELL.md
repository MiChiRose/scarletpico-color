# Archived Clamshell Hardware Plan

Status: shelved on 2026-09-26. Retained as design research; not the current build direction.

The first hardware revision will use a rigid monoblock enclosure. The hinge concept was shelved because a home-built hinge without a dependable detent would introduce wobble, cable fatigue, and a vulnerable mechanical failure point.

## Photographic mock-up — 2026-09-20

The first physical layout photo confirms the basic proportions:

- two nominal 5×7 cm prototyping boards sit side by side, producing a control carrier of roughly 10×7 cm;
- the landscape display PCB is narrower than that carrier and can be centered in an upper shell with useful side bezels;
- both halves can therefore share an outside width of approximately 10–11 cm before wall thickness and tolerances are finalized;
- this is best described as a wide, single-screen clamshell: functionally closer to a Game Boy Advance SP, with the wider stance and control separation associated with a 3DS.

The photo is a component layout, not yet the final case outline. A real hinge needs a gap between the display PCB and the two control boards for hinge barrels, cable bend radius, screw posts, and shell walls. Do not model the parts as touching at the fold line.

## Architecture

ScarletPico Color is one fixed folding console. An RP2350 board runs the emulator, menu, display, microSD access, controls, battery monitoring, and audio. No additional RP2040 is required for the controls.

## Upper half

- 3.5-inch 480×320 ST7796 TFT, landscape.
- Display bezel and rigid rear support so opening the lid does not load the display PCB or glass.
- Flexible interconnect through the hinge, with strain relief on both sides.

## Lower half

- Two solderable prototyping boards used as the first button carrier.
- Four directions, A, B, Start, and Select wired directly to RP2350 GPIO.
- RP2350 board, microSD module, battery, charger/power circuitry, audio DAC or PWM filter as selected, amplifier, speakers, headphone jack, and physical power switch.
- Boards mounted on screws/standoffs; the enclosure, not solder joints, takes button force.
- Joining the two boards electrically from below is acceptable, but they still need a common rigid printed support or independent screw posts. Wire links and solder bridges must not serve as the mechanical hinge between the boards.

## Hinge interconnect

The final wire count depends on where the RP2350 and display breakout are mounted. Two layouts must be compared after measuring the parts:

1. RP2350 in the lower half, display in the lid: route display power and SPI/control signals through the hinge.
2. RP2350 behind the display: route button signals, power, audio, and microSD connections through the hinge.

The first layout keeps most electronics and mass in the base and is the initial preference. Use silicone ultra-flex wire or an FFC/FPC assembly, protect it from sharp printed edges, and test the full opening cycle before final assembly.

The display PCB already provides four mounting holes. The lid should support it at those points with spacers and retain the visible panel with a bezel; the glass itself must not be clamped or used as a structural member.

## Display mapping

Game Boy and Game Boy Color output is 160×144. Exact 2× scaling produces 320×288 on the 480×320 panel, leaving:

- 80 pixels on each side;
- 16 pixels above and below.

These unused areas can be black. Battery status can live in one side rail. Emulation still follows original Game Boy timing; reducing physical display transfers to about 30 updates per second is an optimization, not a change to emulation speed.

## Prototype wiring rules

- Use one ground bus across both prototyping boards.
- Connect each button between its assigned GPIO and ground; use pull-ups and firmware debounce.
- Add a local 100 nF decoupling capacitor near each active board/module where practical.
- Do not power a bare microSD socket from 5 V. Confirm whether the purchased board contains a regulator and level shifting.
- Do not finalize TP4056 charge current until the battery capacity and allowed charge rate are known.
- A basic TP4056 board is not automatically a power-path circuit. Playing while charging requires an explicit load-sharing/power-path design.

## Decisions still needed

- Exact component dimensions and photos of both sides of every module.
- RP2350 and display placement relative to the hinge.
- Measured display PCB width, height, thickness, mounting-hole coordinates, and header position; the photograph is not accurate enough for CAD dimensions.
- Hinge type, maximum opening angle, and flexible interconnect.
- Battery chemistry, capacity, physical size, protection, and charge current.
- Exact audio path, speaker count, headphone switching, and volume control.
- Lid-close detection and behavior: merely blank display, suspend, save and suspend, or full power-off.
- Final GPIO allocation after module pin labels are verified.
