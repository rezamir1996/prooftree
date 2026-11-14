"""Read ProofTree state from the public Studio RPC without trusting a screenshot.

`gen_call` with a read request is enough: no wallet, no signature, no transaction, and
the reply is the contract's return value. This script carries its own small codec for
GenLayer calldata so it needs nothing but Python and curl.

Usage:
    python scripts/read_state.py <address> <method> [arg ...]

    python scripts/read_state.py 0xabc... config
    python scripts/read_state.py 0xabc... verdict_of vendor-a
"""

from __future__ import annotations

import json
import subprocess
import sys

RPC = "https://studio.genlayer.com/api"

TYPE_SPECIAL = 0
TYPE_PINT = 1
TYPE_NINT = 2
TYPE_BYTES = 3
TYPE_STR = 4
TYPE_ARR = 5
TYPE_MAP = 6

SPECIAL_NULL = (0 << 3) | TYPE_SPECIAL
SPECIAL_FALSE = (1 << 3) | TYPE_SPECIAL
SPECIAL_TRUE = (2 << 3) | TYPE_SPECIAL


def _uleb(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def encode(value) -> bytes:
    if value is None:
        return _uleb(SPECIAL_NULL)
    if value is False:
        return _uleb(SPECIAL_FALSE)
    if value is True:
        return _uleb(SPECIAL_TRUE)
    if isinstance(value, int):
        if value >= 0:
            return _uleb((value << 3) | TYPE_PINT)
        return _uleb(((-value - 1) << 3) | TYPE_NINT)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return _uleb((len(raw) << 3) | TYPE_STR) + raw
    if isinstance(value, (bytes, bytearray)):
        return _uleb((len(value) << 3) | TYPE_BYTES) + bytes(value)
    if isinstance(value, (list, tuple)):
        out = bytearray(_uleb((len(value) << 3) | TYPE_ARR))
        for item in value:
            out += encode(item)
        return bytes(out)
    if isinstance(value, dict):
        keys = sorted(value.keys())
        out = bytearray(_uleb((len(keys) << 3) | TYPE_MAP))
        for key in keys:
            raw = key.encode("utf-8")
            out += _uleb(len(raw)) + raw
            out += encode(value[key])
        return bytes(out)
    raise TypeError(f"cannot encode {type(value)!r}")


def decode(mem: bytes):
    pos = 0

    def read_uleb() -> int:
        nonlocal pos
        shift = 0
        result = 0
        while True:
            byte = mem[pos]
            pos += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return result

    def impl():
        nonlocal pos
        code = read_uleb()
        kind = code & 0x07
        if kind == TYPE_SPECIAL:
            if code == SPECIAL_NULL:
                return None
            if code == SPECIAL_FALSE:
                return False
            if code == SPECIAL_TRUE:
                return True
            raise ValueError(f"unsupported special {code}")
        code >>= 3
        if kind == TYPE_PINT:
            return code
        if kind == TYPE_NINT:
            return -code - 1
        if kind == TYPE_BYTES:
            out = mem[pos:pos + code]
            pos += code
            return out
        if kind == TYPE_STR:
            out = mem[pos:pos + code].decode("utf-8")
            pos += code
            return out
        if kind == TYPE_ARR:
            return [impl() for _ in range(code)]
        if kind == TYPE_MAP:
            out = {}
            for _ in range(code):
                length = read_uleb()
                key = mem[pos:pos + length].decode("utf-8")
                pos += length
                out[key] = impl()
            return out
        raise ValueError(f"unsupported type {kind}")

    value = impl()
    if pos != len(mem):
        raise ValueError(f"{len(mem) - pos} trailing bytes")
    return value


def _rlp_bytes(raw: bytes) -> bytes:
    if len(raw) == 1 and raw[0] < 0x80:
        return raw
    if len(raw) < 56:
        return bytes([0x80 + len(raw)]) + raw
    width = (len(raw).bit_length() + 7) // 8
    return bytes([0xB7 + width]) + len(raw).to_bytes(width, "big") + raw


def _rlp_list(items: list) -> bytes:
    payload = b"".join(_rlp_bytes(item) for item in items)
    if len(payload) < 56:
        return bytes([0xC0 + len(payload)]) + payload
    width = (len(payload).bit_length() + 7) // 8
    return bytes([0xF7 + width]) + len(payload).to_bytes(width, "big") + payload


def read(address: str, method: str, args: list):
    payload = {"method": method}
    if args:
        payload["args"] = args
    # The node takes an RLP list: the encoded call and a zero byte marking a read.
    data = _rlp_list([encode(payload), b"\x00"])
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "gen_call",
        "params": [
            {
                "type": "read",
                "to": address,
                "from": "0x0000000000000000000000000000000000000001",
                "data": "0x" + data.hex(),
                "transaction_hash_variant": "latest-nonfinal",
            }
        ],
    }
    proc = subprocess.run(
        [
            "curl", "-s", "-m", "45", "-X", "POST", RPC,
            "-H", "Content-Type: application/json",
            "-H", "Origin: https://studio.genlayer.com",
            "--data-binary", "@-",
        ],
        input=json.dumps(request).encode(),
        capture_output=True,
    )
    reply = json.loads(proc.stdout)
    if "error" in reply:
        return "RPC ERROR: " + json.dumps(reply["error"])[:300]
    return decode(bytes.fromhex(reply["result"]))


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    print(repr(read(sys.argv[1], sys.argv[2], sys.argv[3:])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
