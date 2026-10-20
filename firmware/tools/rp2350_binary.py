"""Read RP2350 UF2 images without confusing the ignored absolute block for flash.

This module does not write to a device. The input is hash-pinned by the build tool.
"""
from pathlib import Path
import hashlib
import struct

FLASH = 0x10000000
FAMILY = 0xE48BFF59
MAGICS = (0x0A324655, 0x9E5D5157, 0x0AB16F30)


def read_image(path):
    raw = Path(path).read_bytes()
    if not raw or len(raw) % 512:
        raise ValueError("Not a complete UF2")
    blocks, other = [], []
    for off in range(0, len(raw), 512):
        block = raw[off:off + 512]
        h = struct.unpack_from("<8I", block)
        if h[:2] != MAGICS[:2] or struct.unpack_from("<I", block, 508)[0] != MAGICS[2]:
            raise ValueError("UF2 magic mismatch")
        if h[7] == FAMILY and h[2] == 0x2000:
            if h[4] != 256:
                raise ValueError("Unexpected application payload size")
            blocks.append((h[3], h[5], h[6], block[32:288]))
        else:
            # picotool emits an absolute ignored block, with its extension tag.
            if h[7] != 0xE48BFF57 or h[2] != 0xA000 or block[288:292] != b"\x04\xe3\x57\x99":
                raise ValueError("Unrecognized non-application block")
            other.append(block)
    blocks.sort()
    if not blocks:
        raise ValueError("No RP2350 ARM Secure application blocks")
    for i, (addr, number, count, payload) in enumerate(blocks):
        if (addr, number, count) != (FLASH + 256 * i, i, len(blocks)):
            raise ValueError("Non-contiguous or duplicate application blocks")
    return b"".join(b[3] for b in blocks), other, hashlib.sha256(raw).hexdigest()


def disassemble(data, start, end):
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
    from capstone.arm import ARM_OP_MEM, ARM_REG_PC
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.skipdata = True
    md.detail = True
    for i in md.disasm(data[start - FLASH:end - FLASH], start):
        extra = ""
        if i.id and i.mnemonic.startswith("ldr") and len(i.operands) > 1:
            op = i.operands[1]
            if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
                addr = ((i.address + 4) & ~3) + op.mem.disp
                if FLASH <= addr < FLASH + len(data) - 4:
                    extra = f" ; [{addr:08x}] = {struct.unpack_from('<I', data, addr - FLASH)[0]:08x}"
        print(f"{i.address:08x} {i.bytes.hex():10} {i.mnemonic:10} {i.op_str}{extra}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("image")
    p.add_argument("--disassemble", nargs=2, type=lambda v: int(v, 0))
    args = p.parse_args()
    data, other, digest = read_image(args.image)
    print(f"SHA256 {digest}; flash bytes {len(data)}; preserved ignored blocks {len(other)}")
    if args.disassemble:
        disassemble(data, *args.disassemble)
