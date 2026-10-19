"""شبیه‌ساز پروتکل MySQL برای سنجش TLS واقعی روی loopback؛ دیتابیس واقعی نیست."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import ssl
import struct
import threading

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from pymysql.constants import CLIENT


def certificate(key, name, issuer, issuer_key, ca, host=None):
    now = datetime.now(timezone.utc)
    builder = (x509.CertificateBuilder().subject_name(name).issuer_name(issuer).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1)).add_extension(x509.BasicConstraints(ca=ca, path_length=None), True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), False)
        .add_extension(x509.KeyUsage(True, False, True, False, False, ca, ca, None, None), True))
    if host:
        builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), False)
        builder = builder.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
    return builder.sign(issuer_key, hashes.SHA256())


def material(folder, host):
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test only CA")])
    root = certificate(root_key, root_name, root_name, root_key, True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    leaf = certificate(key, name, root_name, root_key, False, host)
    ca, cert, private = (Path(folder) / name for name in ("ca.pem", "leaf.pem", "key.pem"))
    ca.write_bytes(root.public_bytes(serialization.Encoding.PEM))
    cert.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    return ca, cert, private


def read_exact(stream, size):
    result = b""
    while len(result) < size:
        block = stream.recv(size - len(result))
        if not block:
            raise EOFError()
        result += block
    return result


def read_packet(stream):
    header = read_exact(stream, 4)
    return read_exact(stream, int.from_bytes(header[:3], "little"))


def send_packet(stream, body, sequence):
    stream.sendall(len(body).to_bytes(3, "little") + bytes([sequence]) + body)


def handshake(tls_enabled):
    capabilities = CLIENT.PROTOCOL_41 | CLIENT.SECURE_CONNECTION | CLIENT.PLUGIN_AUTH | CLIENT.CONNECT_WITH_DB
    if tls_enabled:
        capabilities |= CLIENT.SSL
    return (b"\x0a8.0.0-test\0" + struct.pack("<I", 1) + b"12345678\0" + struct.pack("<H", capabilities & 65535)
            + b"\x2d\x02\0" + struct.pack("<H", capabilities >> 16) + b"\x15" + b"\0" * 10
            + b"abcdefghijkl\0mysql_native_password\0")


def serve(listener, context, state, tls_enabled):
    try:
        with listener.accept()[0] as raw:
            raw.settimeout(5)
            send_packet(raw, handshake(tls_enabled), 0)
            initial = read_packet(raw)
            if not tls_enabled:
                state["plaintext_auth_sent"] = len(initial) > 32
                return
            if len(initial) != 32:
                state["plaintext_auth_sent"] = True
                return
            with context.wrap_socket(raw, server_side=True) as stream:
                read_packet(stream)
                state["tls_auth_received"] = True
                send_packet(stream, b"\0\0\0\x02\0\0\0", 3)
                while True:
                    command = read_packet(stream)
                    if command[:1] == b"\x01":
                        break
                    send_packet(stream, b"\0\0\0\x02\0\0\0", 1)
    except (OSError, EOFError):
        pass


@contextmanager
def server(folder, host="localhost", tls_enabled=True):
    ca, cert, key = material(folder, host)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    state = {"tls_auth_received": False, "plaintext_auth_sent": False}
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(5)
        thread = threading.Thread(target=serve, args=(listener, context, state, tls_enabled), daemon=True)
        thread.start()
        try:
            yield listener.getsockname()[1], ca, state
        finally:
            thread.join(timeout=6)
