package com.phonelink.android.network

/** Wylicza chwilową prędkość (MB/s, dziesiętnie) na podstawie czasu monotonicznego. */
class SpeedTracker {
    private var lastTimeNanos = System.nanoTime()
    private var lastBytes = 0L

    fun speed(currentBytes: Long): Double {
        val now = System.nanoTime()
        val seconds = (now - lastTimeNanos) / 1_000_000_000.0
        val deltaBytes = currentBytes - lastBytes
        lastTimeNanos = now
        lastBytes = currentBytes
        return if (seconds > 0) deltaBytes / seconds / 1_000_000.0 else 0.0
    }
}
