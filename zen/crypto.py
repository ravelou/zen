# -*- encoding:utf-8 -*-

from ecdsa.keys import SigningKey, VerifyingKey
from ecdsa.util import sigencode_der_canonize, sigdecode_der
from ecdsa.curves import SECP256k1

import sys
import base58
import struct
import hashlib
import binascii

__PY3__ = True if sys.version_info[0] >= 3 else False

if not __PY3__:
	from StringIO import StringIO
else:
	from io import BytesIO as StringIO


# byte as int conversion
basint = (lambda e:e) if __PY3__ else \
         (lambda e:ord(e))
# read value as binary data from buffer
unpack =  lambda fmt, fileobj: struct.unpack(fmt, fileobj.read(struct.calcsize(fmt)))
# write value as binary data into buffer
pack = lambda fmt, fileobj, value: fileobj.write(struct.pack(fmt, *value))
# read bytes from buffer
unpack_bytes = lambda f,n: unpack("<"+"%ss"%n, f)[0]
# write bytes into buffer
pack_bytes = (lambda f,v: pack("!"+"%ss"%len(v), f, (v,))) if __PY3__ else \
             (lambda f,v: pack("!"+"c"*len(v), f, v))


def hexlify(data):
	result = binascii.hexlify(data)
	return str(result.decode() if isinstance(result, bytes) else result)


def unhexlify(data):
	if len(data)%2: data = "0"+data
	result = binascii.unhexlify(data)
	return result if isinstance(result, bytes) else result.encode()


def compressEcdsaPublicKey(pubkey):
	first, last = pubkey[:32], pubkey[32:]
	# check if last digit of second part is even (2%2 = 0, 3%2 = 1)
	even = not bool(basint(last[-1]) % 2)
	return (b"\x02" if even else b"\x03") + first

# Uncompressed public key is:
# 0x04 + x-coordinate + y-coordinate
#
# Compressed public key is:
# 0x02 + x-coordinate if y is even
# 0x03 + x-coordinate if y is odd
#
# y^2 mod p = (x^3 + 7) mod p

def uncompressEcdsaPublicKey(pubkey):
	# read more : https://bitcointalk.org/index.php?topic=644919.msg7205689#msg7205689
	p = 0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f
	y_parity = int(pubkey[:2]) - 2
	x = int(pubkey[2:], 16)
	a = (pow(x, 3, p) + 7) % p
	y = pow(a, (p + 1) // 4, p)
	if y % 2 != y_parity:
		y = -y % p
	# return result as der signature (no 0x04 preffix)
	return '{:x}{:x}'.format(x, y)


def getKeys(secret, seed=None):
	"""
    Generate keyring containing public key, signing and checking keys as
    attribute.

    Keyword arguments:
    secret (str or bytes) -- a human pass phrase
    seed (byte) -- a sha256 sequence bytes (private key actualy)

    Return dict
    """
	seed = hashlib.sha256(secret.encode("utf8") if not isinstance(secret, bytes) else secret).digest() if not seed else seed
	signingKey = SigningKey.from_secret_exponent(int(hexlify(seed), 16), SECP256k1, hashlib.sha256)
	publicKey = signingKey.get_verifying_key().to_string()
	return {
		"publicKey": hexlify(compressEcdsaPublicKey(publicKey)),
		"privateKey": hexlify(signingKey.to_string()),
	}


def getSignature(tx, privateKey):
	"""
	Generate transaction signature using private key.

	Arguments:
	tx (dict) -- a transaction description
	privateKey (str) -- a private key as hex string

	Return str
	"""
	signingKey = SigningKey.from_string(unhexlify(privateKey), SECP256k1, hashlib.sha256)
	return hexlify(signingKey.sign_deterministic(getBytes(tx), hashlib.sha256, sigencode=sigencode_der_canonize))


def getSignatureFromBytes(data, privateKey):
	"""
	Generate data signature using private key.

	Arguments:
	data (bytes) -- data in bytes
	privateKey (str) -- a private key as hex string

	Return str
	"""
	signingKey = SigningKey.from_string(unhexlify(privateKey), SECP256k1, hashlib.sha256)
	return hexlify(signingKey.sign_deterministic(data, hashlib.sha256, sigencode=sigencode_der_canonize))


def getId(tx):
	"""
	Generate transaction id.

	Arguments:
	tx (dict) -- a transaction description

	Return str
	"""
	return hexlify(hashlib.sha256(getBytes(tx)).digest())


def getIdFromBytes(data):
	"""
	Generate data id.

	Arguments:
	data (bytes) -- data in bytes

	Return str
	"""
	return hexlify(hashlib.sha256(data).digest())


def verifySignatureFromBytes(data, publicKey, signature):
	"""
	Verify signature.

	Arguments:
	data (bytes) -- data in bytes
	publicKey (str) -- a public key as hex string
	signature (str) -- a signature as hex string

	Return bool
	"""
	if len(publicKey) == 66:
		publicKey = uncompressEcdsaPublicKey(publicKey)
	verifyingKey = VerifyingKey.from_string(unhexlify(publicKey), SECP256k1, hashlib.sha256)
	try:
		verifyingKey.verify(unhexlify(signature), data, hashlib.sha256, sigdecode_der)
	except (BadSignatureError, UnexpectedDER):
		return False
	return True


def getBytes(tx):
	"""
	Hash transaction object into bytes data.

	Argument:
	tx (dict) -- transaction object

	Return bytes sequence
	"""
	buf = StringIO()
	# write type and timestamp
	pack("<bi", buf, (tx["type"], int(tx["timestamp"])))
	# write senderPublicKey as bytes in buffer
	if "senderPublicKey" in tx:
		pack_bytes(buf, unhexlify(tx["senderPublicKey"]))
	# if there is a requesterPublicKey
	if "requesterPublicKey" in tx:
		pack_bytes(buf, unhexlify(tx["requesterPublicKey"]))
	# if there is a recipientId
	if tx.get("recipientId", False):
		recipientId = base58.b58decode_check(tx["recipientId"])
	else:
		recipientId = b"\x00"*21
	pack_bytes(buf, recipientId)
	# if there is a vendorField
	if tx.get("vendorField", False):
		vendorField = tx["vendorField"][:64].ljust(64, "\x00")
	else:
		vendorField = "\x00"*64
	pack_bytes(buf, vendorField.encode("utf8"))
	# write amount and fee value
	pack("<QQ", buf, (int(tx["amount"]), int(tx["fee"])))
	# if there is asset data
	if tx.get("asset", False):
		asset = tx["asset"]
		typ = tx["type"]
		if typ == 1 and "signature" in asset:
			pack_bytes(buf, unhexlify(asset["signature"]["publicKey"]))
		elif typ == 2 and "delegate" in asset:
			pack_bytes(buf, asset["delegate"]["username"].encode("utf-8"))
		elif typ == 3 and "votes" in asset:
			pack_bytes(buf, "".join(asset["votes"]).encode("utf-8"))
		else:
			pass
	# if there is a signature
	if tx.get("signature", False):
		pack_bytes(buf, unhexlify(tx["signature"]))
	# if there is a second signature
	if tx.get("signSignature", False):
		pack_bytes(buf, unhexlify(tx["signSignature"]))

	result = buf.getvalue()
	buf.close()
	return result.encode() if not isinstance(result, bytes) else result


# def bakeTransaction(**kw):
# 	"""
# 	Create transaction localy.

# 	Argument:
# 	tx (dict) -- transaction object

# 	Return dict
# 	"""
# 	if "publicKey" in kw and "privateKey" in kw:
# 		keys = {}
# 		keys["publicKey"] = kw["publicKey"]
# 		keys["privateKey"] = kw["privateKey"]
# 	elif "secret" in kw:
# 		keys = getKeys(kw["secret"])
# 	else:
# 		keys = {}
# 		# raise Exception("Can not initialize transaction (no secret or keys given)")

# 	# put mandatory data
# 	payload = {
# 		"timestamp": kw.get("timestamp", int(slots.getTime())),
# 		"type": int(kw.get("type", 0)),
# 		"amount": int(kw.get("amount", 0)),
# 		"fee": cfg.fees.get({
# 			0: "send",
# 			1: "secondsignature",
# 			2: "delegate",
# 			3: "vote",
# 			# 4: "multisignature",
# 			# 5: "dapp"
# 		}[kw.get("type", 0)])
# 	}

# 	# add optional data
# 	for key in (k for k in ["requesterPublicKey", "recipientId", "vendorField", "asset"] if k in kw):
# 		if kw[key]:
# 			payload[key] = kw[key]

# 	# add sender public key if any key or secret is given
# 	if len(keys):
# 		payload["senderPublicKey"] = keys.get("publicKey", None)

# 	# sign payload if possible
# 	# if len(keys):
# 		payload["signature"] = getSignature(payload, keys["privateKey"])
# 		if kw.get("secondSecret", False):
# 			secondKeys = getKeys(kw["secondSecret"])
# 			payload["signSignature"] = getSignature(payload, secondKeys["privateKey"])
# 		elif kw.get("secondPrivateKey", False):
# 			payload["signSignature"] = getSignature(payload, kw["secondPrivateKey"])
# 		# identify payload
# 		payload["id"] = getId(payload)

# 	return payload
