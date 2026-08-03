package com.phonelink.android.network

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import com.phonelink.android.crypto.CryptoManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.IOException
import java.security.MessageDigest
import java.util.ArrayDeque
import java.util.concurrent.atomic.AtomicLong

/**
 * Realizuje przesyłanie plików zgodnie z file_transfer.py:
 *  - nagłówek FILE_START {filename, size, sha256},
 *  - chunki po 64 KB (każdy zaszyfrowany i poprzedzony 4-bajtową długością),
 *  - potwierdzenie FILE_ACK / błąd ERROR.
 *
 * receiveFile() MUSI być wywoływany z pętli odczytu połączenia (ten sam wątek
 * IO) — kontynuuje czytanie chunków z tego samego gniazda.
 */
class TransferManager(
    private val crypto: CryptoManager,
    private val storage: DownloadStorage,
    private val onTransferUpdated: (TransferItem) -> Unit,
) {

    companion object {
        private const val CHUNK_SIZE = 64 * 1024
    }

    private val idGenerator = AtomicLong(0)
    private val activeSends = ArrayDeque<Long>()
    private val runningItems = HashMap<Long, TransferItem>()
    private val itemsLock = Any()

    private fun nextId(): Long = idGenerator.incrementAndGet()

    fun displayName(resolver: ContentResolver, uri: Uri): String {
        resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                val name = c.getString(0)
                if (!name.isNullOrBlank()) return name
            }
        }
        return "plik_${System.currentTimeMillis()}"
    }

    suspend fun sendFile(conn: ClientConnection, resolver: ContentResolver, uri: Uri) {
        val fileName = displayName(resolver, uri)
        val size = querySize(resolver, uri)
        val item = TransferItem(nextId(), fileName, Direction.SEND, size)
        track(item)
        onTransferUpdated(item)

        try {
            withContext(Dispatchers.IO) {
                val sha256 = computeSha256(resolver, uri)
                conn.writeFrame(
                    "FILE_START",
                    JSONObject()
                        .put("filename", fileName)
                        .put("size", size)
                        .put("sha256", sha256),
                    encrypted = true,
                )

                synchronized(itemsLock) { activeSends.addLast(item.id) }

                val tracker = SpeedTracker()
                var sent = 0L
                val buffer = ByteArray(CHUNK_SIZE)
                val input = resolver.openInputStream(uri)
                    ?: throw IOException("Nie można otworzyć pliku")
                input.use { stream ->
                    while (true) {
                        val read = stream.read(buffer)
                        if (read < 0) break
                        conn.writeChunk(buffer.copyOf(read))
                        sent += read
                        item.update(sent, tracker.speed(sent))
                        onTransferUpdated(item)
                    }
                }
            }
            // Ukończenie potwierdza asynchronicznie FILE_ACK z serwera.
        } catch (e: Exception) {
            item.fail(e.message ?: e.javaClass.simpleName)
            onTransferUpdated(item)
        }
    }

    /** Wywoływane z pętli odczytu — odbiera plik wysyłany przez serwer. */
    suspend fun receiveFile(conn: ClientConnection, frame: ProtocolFrame) {
        val fileName = frame.payload.getString("filename")
        val total = frame.payload.getLong("size")
        val expectedSha = frame.payload.optString("sha256", "")
        val item = TransferItem(nextId(), fileName, Direction.RECEIVE, total)
        track(item)
        onTransferUpdated(item)

        try {
            val (uri, stream) = storage.openSink(fileName)
            val tracker = SpeedTracker()
            val hasher = MessageDigest.getInstance("SHA-256")
            var received = 0L
            try {
                stream.use { sink ->
                    while (received < total) {
                        val chunk = conn.readChunk()
                        sink.write(chunk)
                        hasher.update(chunk)
                        received += chunk.size
                        item.update(received, tracker.speed(received))
                        onTransferUpdated(item)
                    }
                }
            } catch (e: Exception) {
                storage.delete(uri)
                throw e
            }

            val digest = hasher.digest().toHex()
            val ok = expectedSha.isEmpty() || expectedSha.equals(digest, ignoreCase = true)
            item.sha256Ok = ok
            if (ok) {
                item.finishDone(ok = true)
                conn.writeFrame(
                    "FILE_ACK",
                    JSONObject().put("status", "OK").put("saved_path", uri.toString()),
                    encrypted = true,
                )
            } else {
                storage.delete(uri)
                item.fail("SHA-256 mismatch")
                conn.writeFrame(
                    "ERROR",
                    JSONObject().put("error", "SHA-256 mismatch"),
                    encrypted = true,
                )
            }
            onTransferUpdated(item)
        } catch (e: Exception) {
            item.fail(e.message ?: e.javaClass.simpleName)
            onTransferUpdated(item)
        }
    }

    /** FILE_ACK z serwera — potwierdza zakończenie ostatniego wysyłania. */
    fun confirmSend() {
        val id = popActiveSend() ?: return
        val item = findItem(id) ?: return
        item.finishDone(ok = true)
        onTransferUpdated(item)
    }

    /** ERROR z serwera — oznacza ostatnie wysyłanie jako nieudane. */
    fun failActive(frame: ProtocolFrame) {
        val id = popActiveSend() ?: return
        val item = findItem(id) ?: return
        item.fail(frame.payload.optString("error", "Błąd serwera"))
        onTransferUpdated(item)
    }

    private fun popActiveSend(): Long? = synchronized(itemsLock) {
        activeSends.pollLast()
    }

    private fun track(item: TransferItem) {
        synchronized(itemsLock) { runningItems[item.id] = item }
    }

    private fun findItem(id: Long): TransferItem? = synchronized(itemsLock) {
        runningItems[id]
    }

    private fun querySize(resolver: ContentResolver, uri: Uri): Long {
        resolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { c ->
            if (c.moveToFirst() && !c.isNull(0)) return c.getLong(0)
        }
        return 0L
    }

    private fun computeSha256(resolver: ContentResolver, uri: Uri): String {
        val hasher = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(CHUNK_SIZE)
        val stream = resolver.openInputStream(uri)
            ?: throw IOException("Nie można otworzyć pliku do skrótu SHA-256")
        stream.use { input ->
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                hasher.update(buffer, 0, read)
            }
        }
        return hasher.digest().toHex()
    }
}

private fun ByteArray.toHex(): String =
    joinToString("") { byte -> "%02x".format(byte.toInt() and 0xFF) }
