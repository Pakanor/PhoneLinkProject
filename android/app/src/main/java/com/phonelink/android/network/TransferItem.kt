package com.phonelink.android.network

import kotlin.math.min

enum class Direction(val label: String) {
    SEND("Wysyłanie"),
    RECEIVE("Odbieranie"),
}

enum class TransferState {
    RUNNING,
    DONE,
    FAILED,
}

/** Jeden transfer w dashboardzie. Obiekt jest mutowany i ponownie emitowany do StateFlow. */
class TransferItem(
    val id: Long,
    val fileName: String,
    val direction: Direction,
    val totalBytes: Long,
) {
    var bytesSent: Long = 0
    var speedMbps: Double = 0.0
    var sha256Ok: Boolean? = null
    var state: TransferState = TransferState.RUNNING
    var error: String? = null

    val fraction: Float
        get() = if (totalBytes > 0) {
            (bytesSent.toFloat() / totalBytes).coerceIn(0f, 1f)
        } else {
            0f
        }

    val percent: Int get() = (fraction * 100).toInt()

    fun update(bytes: Long, speed: Double) {
        bytesSent = min(bytes, totalBytes)
        speedMbps = speed
    }

    fun finishDone(ok: Boolean) {
        bytesSent = totalBytes
        state = TransferState.DONE
        sha256Ok = ok
    }

    fun fail(message: String) {
        state = TransferState.FAILED
        error = message
    }
}
