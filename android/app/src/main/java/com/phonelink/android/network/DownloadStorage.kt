package com.phonelink.android.network

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import java.io.FilterOutputStream
import java.io.IOException
import java.io.OutputStream

/**
 * Zapis odbieranych plików do publicznego katalogu Pobrane/PhoneLink
 * przez MediaStore (Scoped Storage). Kolizje nazw rozwiązywane sufiksem
 * _1, _2, ... — analogicznie do _open_unique_file() w serwerze Python.
 */
class DownloadStorage(private val context: Context) {

    private val resolver get() = context.contentResolver

    val relativePath: String
        get() = Environment.DIRECTORY_DOWNLOADS + "/PhoneLink"

    fun openSink(baseName: String): Pair<Uri, OutputStream> {
        val displayName = uniqueDisplayName(baseName)
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, displayName)
            put(MediaStore.Downloads.MIME_TYPE, guessMime(displayName))
            put(MediaStore.Downloads.RELATIVE_PATH, relativePath)
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("Nie można utworzyć pliku w katalogu Pobrane")
        val stream = resolver.openOutputStream(uri)
            ?: throw IOException("Nie można otworzyć strumienia zapisu")

        return Pair(
            uri,
            object : FilterOutputStream(stream) {
                override fun close() {
                    try {
                        super.close()
                    } finally {
                        resolver.update(
                            uri,
                            ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) },
                            null,
                            null,
                        )
                    }
                }
            },
        )
    }

    fun delete(uri: Uri) {
        try {
            resolver.delete(uri, null, null)
        } catch (_: Exception) {
        }
    }

    private fun uniqueDisplayName(name: String): String {
        val base = name.substringBeforeLast('.')
        val ext = name.substringAfterLast('.', "")
        var candidate = name
        var counter = 1
        while (exists(candidate)) {
            candidate = if (ext.isEmpty()) "${base}_$counter" else "${base}_$counter.$ext"
            counter++
        }
        return candidate
    }

    private fun exists(displayName: String): Boolean {
        val projection = arrayOf(MediaStore.Downloads._ID)
        val selection = "${MediaStore.Downloads.DISPLAY_NAME} = ? AND " +
            "${MediaStore.Downloads.RELATIVE_PATH} = ?"
        val args = arrayOf(displayName, "$relativePath/")
        resolver.query(
            MediaStore.Downloads.EXTERNAL_CONTENT_URI,
            projection,
            selection,
            args,
            null,
        )?.use { cursor -> return cursor.moveToFirst() }
        return false
    }

    private fun guessMime(fileName: String): String {
        val ext = fileName.substringAfterLast('.', "")
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext.lowercase())
            ?: "application/octet-stream"
    }
}
