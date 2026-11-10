"""
Read the snapshot date from an OSM PBF file's header block, without parsing the data.

Adapted from Aleph (alephgeo/pbf.py: varint, fields, PBF.__init__ header loop).
MIT License, Copyright (c) 2026 Belluxx. https://github.com/Belluxx/Aleph

Format: https://wiki.openstreetmap.org/wiki/PBF_Format. The first blob is an
OSMHeader whose field 32 (osmosis_replication_timestamp) holds the snapshot time
in seconds since the epoch; Geofabrik extracts always set it.
"""
import struct
import zlib
from datetime import datetime, timezone


def _varint(data, offset):
    value = shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
        shift += 7
    raise ValueError("Invalid PBF varint.")


def _fields(data):
    """Yield (field number, value) from a protobuf message (varint and length-delimited only)."""
    offset = 0
    while offset < len(data):
        key, offset = _varint(data, offset)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, offset = _varint(data, offset)
        elif wire == 2:
            size, offset = _varint(data, offset)
            value, offset = data[offset:offset + size], offset + size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value, offset = data[offset:offset + size], offset + size
        else:
            raise ValueError("Unsupported PBF wire type.")
        yield number, value


def _blob_data(blob):
    fields = dict(_fields(blob))
    if 1 in fields:  # raw
        return fields[1]
    if 3 in fields:  # zlib_data
        return zlib.decompress(fields[3])
    raise ValueError("Unsupported PBF header compression.")


def snapshot_time(path):
    """Snapshot time of a PBF as an aware UTC datetime, or None if the header has none."""
    with open(path, "rb") as fh:
        raw = fh.read(4)
        if len(raw) != 4:
            raise ValueError("Not a PBF file.")
        (length,) = struct.unpack(">I", raw)
        if not 0 < length < 65536:
            raise ValueError("Invalid PBF block header.")
        header = dict(_fields(fh.read(length)))
        if header.get(1) != b"OSMHeader":
            raise ValueError("PBF does not start with an OSMHeader block.")
        blob = fh.read(header.get(3, 0))
    for number, value in _fields(_blob_data(blob)):
        if number == 32 and value:
            return datetime.fromtimestamp(value, timezone.utc)
    return None
