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

import select
import socket
import struct

ETH_P_IP = 0x0800
ETH_P_8021Q = 0x8100
ETH_P_ALL = 0x0003
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


def list_interfaces() -> list[str]:
    """Return the names of the up, non-loopback interfaces to sniff.

    The AF_PACKET wildcard bind (an empty interface name, or ``"any"``) is not
    portable: on kernels where WSL2 and several container runtimes are enabled
    it fails with ``ENODEV`` ("No such device"), which would silently kill the
    sniffer.  Enumerating real interface names avoids the wildcard entirely.

    Falls back to ``["lo"]`` when nothing else is up so the caller still gets a
    usable socket instead of an immediate failure.
    """
    names: list[str] = []

    try:
        names = [name for _, name in socket.if_nameindex()]
    except OSError:
        names = []

    if not names:
        return ["lo"]

    usable = []

    for name in names:
        try:
            flags = _interface_flags(name)
        except OSError:
            continue

        # Skip interfaces that are administratively down.
        if not flags & _IFF_UP:
            continue

        usable.append(name)

    if not usable:
        return ["lo"]

    # Sniff the loopback last so real traffic is reported first.
    usable.sort(key=lambda name: name == "lo")

    return usable


def _interface_flags(name: str) -> int:
    """Return the SIOCGIFFLAGS value for ``name``."""
    import fcntl

    request = struct.pack("256s", name.encode()[:15])

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        return struct.unpack("H", fcntl.ioctl(probe, 0x8913, request)[16:18])[0]


_IFF_UP = 0x1


def _open_capture_socket(interface: str) -> socket.socket:
    """Open a CAP_NET_RAW AF_PACKET socket bound to ``interface``.

    The socket is opened with ``ETH_P_ALL`` on purpose.  Linux delivers
    *outgoing* frames only to packet sockets registered for ``ETH_P_ALL``
    (``dev_queue_xmit_nit()`` walks the ``ptype_all`` list); a socket opened
    with a specific protocol such as ``ETH_P_IP`` is only fed on the receive
    path.  A protocol-specific socket would therefore only ever see the DNS
    *responses* coming back from the resolver - and never the queries this
    daemon exists to detect.  :func:`parse_packet` filters out the frames
    that are of no interest (ARP, IPv6, non-UDP, other ports).
    """
    handle = socket.socket(
        socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL)
    )

    try:
        handle.bind((interface, 0))
    except OSError:
        handle.close()
        raise

    return handle


def sniff(handle_packet, interface: str | None = None, should_stop=None):
    """Sniff UDP/53 frames until ``should_stop`` returns True.

    ``handle_packet`` receives the parsed packet dict.  Any socket/privilege
    error is raised to the caller so it can be logged and the thread ended.

    When ``interface`` is None every up interface is watched (see
    :func:`list_interfaces`); frames from the loopback interface are delivered
    too, which is where a local stub resolver such as ``systemd-resolved``
    sends its queries.
    """
    interfaces = [interface] if interface else list_interfaces()

    handles = [_open_capture_socket(name) for name in interfaces]

    try:
        while should_stop is None or not should_stop():
            try:
                readable, _, _ = select.select(handles, [], [], 1.0)
            except OSError:
                continue

            for handle in readable:
                try:
                    frame = handle.recv(65535)
                except OSError:
                    continue

                packet = parse_packet(frame)

                if packet is not None:
                    handle_packet(packet)
    finally:
        for handle in handles:
            handle.close()

