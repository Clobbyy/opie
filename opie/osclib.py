"""
Minimal OSC 1.0 encoder/decoder — pure Python standard library, zero dependencies.

We only need what ETC Eos accepts: an address pattern plus int32 (i), float32 (f),
and string (s) arguments. That's it. No bundles on the send side. The decoder
handles plain messages (and skips a #bundle header) so osc_sniffer.py can read back
what we send during loopback testing.

OSC reference: https://opensoundcontrol.stanford.edu/spec-1_0.html
"""

import struct


def _osc_string(s: str) -> bytes:
    """Encode an OSC-string: UTF-8 bytes, NUL-terminated, padded to a 4-byte boundary."""
    b = s.encode("utf-8") + b"\x00"
    while len(b) % 4 != 0:
        b += b"\x00"
    return b


def encode(address: str, args=None) -> bytes:
    """
    Build a single OSC message.

    args items may be:
      - bool  -> sent as int32 0/1 (Eos has no use for OSC T/F here)
      - int   -> int32 'i'
      - float -> float32 'f'
      - str   -> OSC-string 's'
    """
    args = args or []
    out = _osc_string(address)
    typetag = ","
    payload = b""
    for a in args:
        # bool is a subclass of int, so test it first.
        if isinstance(a, bool):
            typetag += "i"
            payload += struct.pack(">i", 1 if a else 0)
        elif isinstance(a, int):
            typetag += "i"
            payload += struct.pack(">i", a)
        elif isinstance(a, float):
            typetag += "f"
            payload += struct.pack(">f", a)
        elif isinstance(a, str):
            typetag += "s"
            payload += _osc_string(a)
        else:
            raise TypeError(f"Unsupported OSC argument type: {type(a)!r}")
    return out + _osc_string(typetag) + payload


def _read_string(data: bytes, idx: int):
    """Read an OSC-string starting at idx; return (text, next_index)."""
    end = data.index(b"\x00", idx)
    text = data[idx:end].decode("utf-8", errors="replace")
    # advance past the NUL and any padding up to the next 4-byte boundary
    nxt = end + 1
    while nxt % 4 != 0:
        nxt += 1
    return text, nxt


def decode(data: bytes):
    """
    Decode a single OSC message into (address, [args]).
    Returns (None, []) for things we don't bother parsing (e.g. bundles).
    """
    if data.startswith(b"#bundle"):
        return None, []  # sniffer only needs our plain outgoing messages
    address, idx = _read_string(data, 0)
    if idx >= len(data) or data[idx : idx + 1] != b",":
        return address, []
    typetag, idx = _read_string(data, idx)
    args = []
    for t in typetag[1:]:
        if t == "i":
            (val,) = struct.unpack(">i", data[idx : idx + 4])
            idx += 4
            args.append(val)
        elif t == "f":
            (val,) = struct.unpack(">f", data[idx : idx + 4])
            idx += 4
            args.append(round(val, 4))
        elif t == "s":
            val, idx = _read_string(data, idx)
            args.append(val)
        else:
            # unknown type tag — stop, we can't know its width
            break
    return address, args


def format_message(address: str, args) -> str:
    """Human-readable one-liner, e.g. '/eos/chan/5  [50.0]'."""
    return f"{address}  {args}" if args else address
