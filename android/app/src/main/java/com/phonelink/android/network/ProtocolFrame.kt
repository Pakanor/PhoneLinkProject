package com.phonelink.android.network

import com.phonelink.android.crypto.CryptoManager
import org.json.JSONObject
import java.io.EOFException
import java.io.IOException
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Ramka protokołu PhoneLink, identyczna z Pythonem (protocol.py):
 *
 *   [ 4 bajty długości big-endian (struct.pack("!I")) ][ payload ]
 *
 * gdzie payload to JSON {"type": ..., "payload": {...}}. Jeżeli [encrypted]
 * jest włączone, JSON jest szyfrowany AES-256-GCM (nonce 12B || ciphertext || tag 16B),
 * a prefiks długości opisuje zaszyfrowane dane.
 */
data class ProtocolFrame(
    val type: String,
    val payload: JSONObject,
)

object FrameCodec {

    private const val MAX_FRAME_SIZE = 64 * 1024 * 1024

    fun encodeFrame(type: String, payload: JSONObject, crypto: CryptoManager?): ByteArray {
        var body = JSONObject()
            .put("type", type)
            .put("payload", payload)
            .toString()
            .toByteArray(Charsets.UTF_8)
        if (crypto != null) {
            body = crypto.encrypt(body)
        }
        val prefix = ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN).putInt(body.size).array()
        return prefix + body
    }

    fun readFrame(input: InputStream, crypto: CryptoManager?): ProtocolFrame {
        val prefix = readExact(input, 4)
        val length = ByteBuffer.wrap(prefix).order(ByteOrder.BIG_ENDIAN).int
        if (length <= 0 || length > MAX_FRAME_SIZE) {
            throw IOException("Nieprawidłowa długość ramki: $length")
        }
        var body = readExact(input, length)
        if (crypto != null) {
            body = crypto.decrypt(body)
        }
        val json = JSONObject(String(body, Charsets.UTF_8))
        return ProtocolFrame(json.getString("type"), json.getJSONObject("payload"))
    }

    /** Wysyła chunk: 4B długości zaszyfrowanego chunku + dane (jak recv_file/send_file w Pythonie). */
    fun writeChunk(output: java.io.OutputStream, data: ByteArray, crypto: CryptoManager) {
        val wrapped = crypto.encrypt(data)
        output.write(ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN).putInt(wrapped.size).array())
        output.write(wrapped)
        output.flush()
    }

    /** Czyta i odszyfrowuje chunk z prefiksem długości. */
    fun readChunk(input: InputStream, crypto: CryptoManager): ByteArray {
        val prefix = readExact(input, 4)
        val length = ByteBuffer.wrap(prefix).order(ByteOrder.BIG_ENDIAN).int
        if (length <= 0 || length > MAX_FRAME_SIZE) {
            throw IOException("Nieprawidłowa długość chunku: $length")
        }
        val data = readExact(input, length)
        return crypto.decrypt(data)
    }

    fun readExact(input: InputStream, n: Int): ByteArray {
        val buffer = ByteArray(n)
        var offset = 0
        while (offset < n) {
            val read = input.read(buffer, offset, n - offset)
            if (read < 0) {
                throw EOFException("Połączenie zamknięte (odebrano $offset/$n bajtów)")
            }
            offset += read
        }
        return buffer
    }
}
