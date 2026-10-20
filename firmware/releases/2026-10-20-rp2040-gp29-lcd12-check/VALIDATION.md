# LCD12 diagnostic validation — 2026-10-20

UF2 SHA-256: `193cdaac72fce5e4ea8268db2719715ddd5397f74138694c9456332074a90c03`.
Normal 100 MHz UF2 preserved unchanged:
`dd4b003c5014082b2828f8454f094c75ecee98a56fdc634c5bd0b660d17affce`.

Build audit passes RP2040 UF2/ARMv6-M target, flash boundary, RAM headroom
27,284 B, identical core header and display-driver source vs 2.2.3 baseline.

Actual compiled ELF test passed:

```sh
python firmware/tests/test_rp2350_menu_arm.py --rp2040 --elf firmware/build-rp2040-gp29-lcd12/scarlet2040.elf --battery-adc --expected-lcd-hz 12500000
```

Menu/settings/pause/exit, snapshot ABI, audio scheduling/DMA isolation,
frame ownership, GB/GBC synthetic ROM execution, GP29-only sampling,
persistence/voltage/error/low handling and indicator bounds passed.
The actual `display_game_speed` function requests 12,500,000 Hz at SPI0.
SDK peripherals are mocked: this DOES NOT simulate real signal integrity
or reproduce/confirm a fix for the user's unreadable panel.

User tentatively recalls previous working version 2.2.1. The 2.2.3 source
base was not confirmed hardware-working. No automatic flash or USB access.
