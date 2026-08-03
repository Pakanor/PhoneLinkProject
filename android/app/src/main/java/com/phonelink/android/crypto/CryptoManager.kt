package com.phonelink.android.crypto

import java.math.BigInteger
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.SecureRandom
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPublicKeySpec
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.Mac
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * CryptoLayer zgodny bajt-po-bajcie z serwerem PhoneLink (Python).
 *
 * - ECDH na krzywej SECP256R1 (P-256), klucze publiczne wymieniane jako
 *   Base64 punktu X9.62 (0x04 || X[32] || Y[32]).
 * - Wyprowadzanie klucza AES-256 przez HKDF-SHA256:
 *   salt = 32 bajty zer, info = b"phonelink-ecdhe-aes256gcm", length = 32.
 * - AES-256-GCM: nonce 12B dołączany przed szyfrogramem, tag 16B na końcu
 *   (dokładnie jak AESGCM.encrypt() w bibliotece cryptography Pythona).
 */
class CryptoManager {

    companion object {
        const val NONCE_SIZE = 12
        const val TAG_SIZE = 16
        const val KEY_SIZE = 32
        const val CURVE_NAME = "secp256r1"
        val HKDF_INFO = "phonelink-ecdhe-aes256gcm".toByteArray(Charsets.UTF_8)
    }

    private val keyFactory: KeyFactory = KeyFactory.getInstance("EC")

    private val keyPair: KeyPair = KeyPairGenerator.getInstance("EC").apply {
        initialize(ECGenParameterSpec(CURVE_NAME), SecureRandom())
    }.generateKeyPair()

    private val p256Params: ECParameterSpec = (keyPair.public as ECPublicKey).params

    private var aesKey: SecretKey? = null

    /** Klucz publiczny klienta jako Base64 punktu X9.62 (identyczny jak w Pythonie). */
    val publicKeyPointB64: String by lazy {
        Base64.getEncoder().encodeToString(encodeUncompressedPoint(keyPair.public as ECPublicKey))
    }

    private fun encodeUncompressedPoint(pub: ECPublicKey): ByteArray {
        val x = toFixed(pub.w.affineX, 32)
        val y = toFixed(pub.w.affineY, 32)
        return byteArrayOf(0x04) + x + y
    }

    private fun toFixed(value: BigInteger, size: Int): ByteArray {
        val raw = value.toByteArray()
        return if (raw.size >= size) {
            raw.copyOfRange(raw.size - size, raw.size)
        } else {
            ByteArray(size - raw.size) + raw
        }
    }

    /**
     * Oblicza shared secret ECDH i wyprowadza klucz AES-256 (HKDF-SHA256).
     * [serverPubKeyB64] to klucz publiczny serwera (Base64 punktu X9.62).
     */
    fun deriveSharedKey(serverPubKeyB64: String): SecretKey {
        val point = Base64.getDecoder().decode(serverPubKeyB64)
        require(point.size == 65 && point[0] == 0x04.toByte()) {
            "Nieprawidłowy klucz publiczny serwera (oczekiwano punktu X9.62)"
        }
        val x = BigInteger(1, point.copyOfRange(1, 33))
        val y = BigInteger(1, point.copyOfRange(33, 65))
        val serverPublicKey = keyFactory.generatePublic(ECPublicKeySpec(ECPoint(x, y), p256Params))

        val agreement = KeyAgreement.getInstance("ECDH")
        agreement.init(keyPair.private)
        agreement.doPhase(serverPublicKey, true)
        val sharedSecret = agreement.generateSecret()

        val key = deriveAesKey(sharedSecret)
        aesKey = key
        return key
    }

    private fun deriveAesKey(ikm: ByteArray): SecretKey {
        val prk = hmac(ByteArray(KEY_SIZE), ikm) // extract: salt = 32 zer (jak salt=None w Pythonie)
        val okm = hkdfExpand(prk, HKDF_INFO, KEY_SIZE)
        return SecretKeySpec(okm, "AES")
    }

    private fun hmac(key: ByteArray, data: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal(data)
    }

    private fun hkdfExpand(prk: ByteArray, info: ByteArray, length: Int): ByteArray {
        val blocks = mutableListOf<ByteArray>()
        var previous = ByteArray(0)
        var counter = 1
        var produced = 0
        while (produced < length) {
            val block = hmac(prk, previous + info + byteArrayOf(counter.toByte()))
            blocks.add(block)
            previous = block
            produced += block.size
            counter++
        }
        val joined = blocks.reduce { acc, b -> acc + b }
        return joined.copyOf(length)
    }

    /** [plaintext] -> nonce(12B) || ciphertext(|| tag 16B). */
    fun encrypt(plaintext: ByteArray): ByteArray {
        val key = deriveOrThrow()
        val nonce = ByteArray(NONCE_SIZE).also { SecureRandom().nextBytes(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(TAG_SIZE * 8, nonce))
        return nonce + cipher.doFinal(plaintext)
    }

    /** Odszyfrowuje dane w formacie nonce(12B) || ciphertext(|| tag 16B). */
    fun decrypt(data: ByteArray): ByteArray {
        val key = deriveOrThrow()
        require(data.size > NONCE_SIZE) { "Zbyt krótkie dane szyfrogramu" }
        val nonce = data.copyOfRange(0, NONCE_SIZE)
        val body = data.copyOfRange(NONCE_SIZE, data.size)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(TAG_SIZE * 8, nonce))
        return cipher.doFinal(body)
    }

    val hasAesKey: Boolean get() = aesKey != null

    private fun deriveOrThrow(): SecretKey =
        aesKey ?: throw IllegalStateException("Brak wyprowadzonego klucza AES")
}
