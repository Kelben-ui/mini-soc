"""Minimal DNS query sniffer for the Mini SOC IDS (task 4.5).

Reads UDP/53 packets straight off the wire with an ``AF_PACKET`` raw socket
(no third-party dependency) and returns the queried name.  This needs
``CAP_NET_RAW`` (or root); the packaged ``mini-soc-ids.service`` grants the
capability to the dedicated ``mini-soc-ids`` user.

The parsing helpers are deliberately pure functions so they can be unit
tested with synthetic frames on any platform; only :func:`sniff` touches the
Linux raw socket.
"""

from __future__ import annotations

import socket
import struct

ETH_P_IP = 0x0800
ETH_P_8021Q = 0x8100
IPPROTO_UDP = 17


def parse_dns_name(payload: bytes, offset: int):
    """Return ``(name, new_offset)`` for a DNS QNAME at ``offset``.

    Compression pointers are not followed (a query name is never compressed).
    Returns ``(None, offset)`` when the name is malformed.
    """
    labels = []
    position = offset

    while position < len(payload):
        length = payload[position]

        if length == 0:
            position += 1
            name = ".".join(labels) if labels else ""
            return name, position

        # A Query name uses at most 63-byte labels; anything else is a
        # compression pointer or junk we do not follow.
        if length & 0xC0:
            return None, offset

        position += 1

        if position + length > len(payload):
            return None, offset

        labels.append(payload[position : position + length].decode("latin-1"))
        position += length

    return None, offset


def parse_dns_query(payload: bytes):
    """Return the QNAME of a DNS query, or ``None``.

    ``payload`` is the UDP payload.  Only queries (QR=0) with at least one
    question are parsed.
    """
    if len(payload) < 12:
        return None

    flags = struct.unpack_from("!H", payload, 2)[0]
    qdcount = struct.unpack_from("!H", payload, 4)[0]

    if flags & 0x8000 or qdcount == 0:
        return None

    name, _ = parse_dns_name(payload, 12)

    if not name:
        return None

    return name


def parse_packet(frame: bytes):
    """Parse an Ethernet frame into ``{src_ip, dst_ip, sport, dport, qname}``.

    Returns ``None`` unless the frame is IPv4/UDP to or from port 53 carrying a
    parseable DNS query.
    """
    if len(frame) < 14:
        return None

    ethertype = struct.unpack_from("!H", frame, 12)[0]
    offset = 14

    # Allow a single 802.1Q VLAN tag.
    if ethertype == ETH_P_8021Q:
        if len(frame) < 18:
            return None
        ethertype = struct.unpack_from("!H", frame, 16)[0]
        offset = 18

    if ethertype != ETH_P_IP:
        return None

    if len(frame) < offset + 20:
        return None

    ihl = (frame[offset] & 0x0F) * 4

    if ihl < 20 or len(frame) < offset + ihl + 8:
        return None

    if frame[offset + 9] != IPPROTO_UDP:
        return None

    src_ip = socket.inet_ntoa(frame[offset + 12 : offset + 16])
    dst_ip = socket.inet_ntoa(frame[offset + 16 : offset + 20])

    udp = offset + ihl
    sport, dport, length = struct.unpack_from("!HHH", frame, udp)

    if dport != 53 and sport != 53:
        return None

    payload = frame[udp + 8 : udp + length]

    qname = parse_dns_query(payload)

    if not qname:
        return None

    return {
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "sport": sport,
        "dport": dport,
        "qname": qname,
    }


def sniff(handle_packet, interface: str | None = None, should_stop=None):
    """Sniff UDP/53 frames until ``should_stop`` returns True.

    ``handle_packet`` receives the parsed packet dict.  Any socket/privilege
    error is raised to the caller so it can be logged and the thread ended.
    """
    handle = socket.socket(
        socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_IP)
    )

    try:
        handle.bind((interface or "", 0))
    except OSError:
        # Binding an interface that does not exist; fall back to all.
        handle.bind(("", 0))

    try:
        while should_stop is None or not should_stop():
            try:
                frame = handle.recv(65535)
            except OSError:
                continue

            packet = parse_packet(frame)

            if packet is not None:
                handle_packet(packet)
    finally:
        handle.close()
