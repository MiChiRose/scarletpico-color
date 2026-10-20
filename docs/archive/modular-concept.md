# Archived Modular Concept

Status: shelved on 2026-09-20. This is not the current build direction.

The earlier concept used a standalone display "head" with magnetic pogo-pin attachments for game controls and music controls. It considered smart modules with RP2040 controllers, passive audio modules, module identification, hot-plug detection, switched 5 V power, UART or a one-wire data bus, and I2S audio.

The proposed compact connector used nine contacts:

1. GND
2. GND
3. switched 5 V
4. switched 5 V
5. half-duplex data
6. combined module detect/ID
7. I2S data
8. I2S bit clock
9. I2S left/right clock

This approach was set aside in favor of a fixed clamshell console. The archive exists so the module research can be resumed later without constraining the current hardware.
