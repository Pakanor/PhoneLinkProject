package com.phonelink.android.network

import com.phonelink.android.crypto.CryptoManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.IOException
import java.io.InputStream
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Połączenie TCP z serwerem PhoneLink. Kolejność (identyczna z handshake.py):
 *
 * 1. HANDSHAKE      (jawny)      {version, supported_ciphers, client_pub_key}
 * 2. HANDSHAKE_ACK  (jawny)      {cipher_selected, server_pub_key}
 * 3. HANDSHAKE_DONE (szyfrowany) {status: "OK"}
 * 4. GREETING       (szyfrowany) {user, action}
 * 5. GREETING_ACK   (szyfrowany) {status: "OK"}
 *
 * Po uzgodnieniu klucza startuje pętla odczytu ramek (FILE_START/FILE_ACK/ERROR).
 */
class ClientConnection(
    private val host: String,
    private val port: Int,
    private val crypto: CryptoManager,
) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val transferMutex = Mutex()

    private var socket: Socket? = null
    private var input: InputStream? = null
    private var output: BufferedOutputStream? = null
    private var readLoopJob: Job? = null

    @Volatile
    var running = false
        private set

    /** Wywoływany z wątku IO dla każdej odebranej, zaszyfrowanej ramki. */
    var onFrame: (suspend (ProtocolFrame) -> Unit)? = null

    /** Wywoływany, gdy pętla odczytu kończy się z powodu błędu/rozłączenia. */
    var onClosed: ((Throwable?) -> Unit)? = null

    suspend fun connect() = withContext(Dispatchers.IO) {
        val sock = Socket()
        try {
            sock.connect(InetSocketAddress(host, port), 10_000)
            sock.tcpNoDelay = true
            socket = sock
            input = BufferedInputStream(sock.getInputStream(), 64 * 1024)
            output = BufferedOutputStream(sock.getOutputStream(), 64 * 1024)

            writeFrame(
                "HANDSHAKE",
                JSONObject()
                    .put("version", "1.0")
                    .put("supported_ciphers", JSONArray().put("AES-256-GCM"))
                    .put("client_pub_key", crypto.publicKeyPointB64),
                encrypted = false,
            )

            val ack = readFrame(encrypted = false)
            require(ack.type == "HANDSHAKE_ACK") { "Oczekiwano HANDSHAKE_ACK, otrzymano ${ack.type}" }
            val serverPubKey = ack.payload.getString("server_pub_key")
            crypto.deriveSharedKey(serverPubKey)

            writeFrame("HANDSHAKE_DONE", JSONObject().put("status", "OK"), encrypted = true)
            writeFrame(
                "GREETING",
                JSONObject().put("user", "android").put("action", "connect"),
                encrypted = true,
            )

            val greetingAck = readFrame(encrypted = true)
            require(greetingAck.type == "GREETING_ACK") {
                "Oczekiwano GREETING_ACK, otrzymano ${greetingAck.type}"
            }
        } catch (e: Exception) {
            close()
            throw e
        }
    }

    fun startReadLoop() {
        if (running) return
        running = true
        readLoopJob = scope.launch {
            try {
                while (running) {
                    val frame = readFrame(encrypted = true)
                    onFrame?.invoke(frame)
                }
            } catch (e: Exception) {
                if (running) {
                    onClosed?.invoke(e)
                }
            } finally {
                running = false
            }
        }
    }

    suspend fun writeFrame(type: String, payload: JSONObject, encrypted: Boolean) =
        transferMutex.withLock {
            withContext(Dispatchers.IO) {
                val bytes = FrameCodec.encodeFrame(type, payload, if (encrypted) crypto else null)
                output!!.write(bytes)
                output!!.flush()
            }
        }

    suspend fun readFrame(encrypted: Boolean): ProtocolFrame = withContext(Dispatchers.IO) {
        FrameCodec.readFrame(input!!, if (encrypted) crypto else null)
    }

    /** Wysyła pojedynczy 64 KB chunk pliku (zaszyfrowany, z prefiksem długości). */
    suspend fun writeChunk(data: ByteArray) = transferMutex.withLock {
        withContext(Dispatchers.IO) {
            FrameCodec.writeChunk(output!!, data, crypto)
        }
    }

    /** Czyta pojedynczy chunk pliku z gniazda. Wywołuj wyłącznie z pętli odczytu. */
    suspend fun readChunk(): ByteArray = withContext(Dispatchers.IO) {
        FrameCodec.readChunk(input!!, crypto)
    }

    fun close() {
        running = false
        try {
            socket?.close()
        } catch (_: IOException) {
        }
        socket = null
        input = null
        output = null
        readLoopJob?.cancel()
        scope.cancel()
    }
}
