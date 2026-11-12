"""AES-GCM: AAD links a record to the table, subject, day and key version."""

import base64, hashlib, hmac, json, os, secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def b64(b):
    return base64.urlsafe_b64encode(b).decode()


def raw(s):
    return base64.b64decode(s, altchars=b"-_", validate=True)


def fresh():
    return {
        "active": "v1",
        "keys": {"v1": b64(AESGCM.generate_key(bit_length=256))},
        "pseudonym": b64(os.urandom(32)),
    }


def write_private(path, data, replace=False):
    tmp = path.with_suffix("." + secrets.token_hex(8) + ".tmp")
    with os.fdopen(
        os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf8"
    ) as f:
        json.dump(data, f)
    if replace:
        os.replace(tmp, path)
    else:
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass
        finally:
            tmp.unlink(missing_ok=True)


def read_ring(settings, create=False):
    if settings.mode == "supabase":
        ring = json.loads(os.environ["ALZACE_KEYRING"])
    else:
        path = settings.directory / "keys.json"
        if create and not path.exists():
            write_private(path, fresh())
        if not path.is_file():
            raise RuntimeError("Inicialice la demo con python -m backend.cli init")
        ring = json.loads(path.read_text(encoding="utf8"))
    if (
        len(raw(ring["keys"][ring["active"]])) != 32
        or len(raw(ring["pseudonym"])) != 32
    ):
        raise RuntimeError("El llavero requiere claves de 256 bits")
    return ring


def pseudo(ring, external):
    return hmac.new(
        raw(ring["pseudonym"]), ("fitbit:" + external).encode(), hashlib.sha256
    ).hexdigest()


def aad(table, owner, day, version):
    return json.dumps([table, owner, day, version], separators=(",", ":")).encode()


def encrypt(ring, table, owner, day, data):
    ver = ring["active"]
    nonce = os.urandom(12)
    key = AESGCM(raw(ring["keys"][ver]))
    return dict(
        version=ver,
        blob=nonce
        + key.encrypt(
            nonce,
            json.dumps(data, allow_nan=False).encode(),
            aad(table, owner, day, ver),
        ),
    )


def decrypt(ring, table, row):
    ver = row["version"]
    blob = row["blob"]
    return json.loads(
        AESGCM(raw(ring["keys"][ver])).decrypt(
            blob[:12], blob[12:], aad(table, row["owner"], row["day"], ver)
        )
    )
