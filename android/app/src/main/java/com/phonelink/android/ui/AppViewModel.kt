package com.phonelink.android.ui

import android.app.Application
import android.content.ContentResolver
import android.net.Uri
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.phonelink.android.crypto.CryptoManager
import com.phonelink.android.discovery.DiscoveredServer
import com.phonelink.android.discovery.NsdDiscoveryManager
import com.phonelink.android.network.ClientConnection
import com.phonelink.android.network.ConnectionState
import com.phonelink.android.network.DownloadStorage
import com.phonelink.android.network.ProtocolFrame
import com.phonelink.android.network.TransferItem
import com.phonelink.android.network.TransferManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class AppViewModel(application: Application) : AndroidViewModel(application) {

    private val discoveryManager = NsdDiscoveryManager(application)
    private val cryptoManager = CryptoManager()
    private val storage = DownloadStorage(application)
    private val transferManager = TransferManager(
        crypto = cryptoManager,
        storage = storage,
        onTransferUpdated = ::updateTransfer,
    )

    private var connection: ClientConnection? = null

    val servers: StateFlow<List<DiscoveredServer>> = discoveryManager.servers

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    val scanning: StateFlow<Boolean> = discoveryManager.scanning

    private val _transfers = MutableStateFlow<List<TransferItem>>(emptyList())
    val transfers: StateFlow<List<TransferItem>> = _transfers.asStateFlow()

    private val _pendingShareUris = MutableStateFlow<List<Uri>>(emptyList())
    val pendingShareUris: StateFlow<List<Uri>> = _pendingShareUris.asStateFlow()

    fun scanNetwork() {
        discoveryManager.startDiscovery()
    }

    fun connectTo(server: DiscoveredServer) {
        if (connection != null) return
        _connectionState.value = ConnectionState.CONNECTING

        val conn = ClientConnection(server.host, server.port, cryptoManager)
        conn.onFrame = { frame -> handleFrame(conn, frame) }
        conn.onClosed = { _ ->
            conn.close()
            connection = null
            _connectionState.value = ConnectionState.DISCONNECTED
        }
        connection = conn

        viewModelScope.launch {
            try {
                conn.connect()
                conn.startReadLoop()
                _connectionState.value = ConnectionState.CONNECTED
            } catch (e: Exception) {
                connection = null
                _connectionState.value = ConnectionState.DISCONNECTED
            }
        }
    }

    fun disconnect() {
        connection?.close()
        connection = null
        _connectionState.value = ConnectionState.DISCONNECTED
    }

    /** Obsługa ramek z pętli odczytu (wątek IO). */
    private suspend fun handleFrame(conn: ClientConnection, frame: ProtocolFrame) {
        when (frame.type) {
            "FILE_START" -> transferManager.receiveFile(conn, frame)
            "FILE_ACK" -> transferManager.confirmSend()
            "ERROR" -> transferManager.failActive(frame)
        }
    }

    fun sendFiles(uris: List<Uri>) {
        val conn = connection ?: return
        val resolver: ContentResolver = getApplication<Application>().contentResolver
        viewModelScope.launch {
            uris.forEach { uri ->
                persistReadPermission(uri)
                transferManager.sendFile(conn, resolver, uri)
            }
        }
    }

    /** Pliki dostarczone przez ACTION_SEND / ACTION_SEND_MULTIPLE (Udostępnij…). */
    fun queueIncomingShare(uris: List<Uri>) {
        uris.forEach { persistReadPermission(it) }
        _pendingShareUris.update { (it + uris).distinct() }
    }

    fun sendPendingShares() {
        val pending = _pendingShareUris.value
        if (pending.isEmpty()) return
        _pendingShareUris.value = emptyList()
        sendFiles(pending)
    }

    private fun persistReadPermission(uri: Uri) {
        if (Build.VERSION.SDK_INT >= 33) {
            try {
                getApplication<Application>().contentResolver
                    .takePersistableUriPermission(
                        uri,
                        android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION,
                    )
            } catch (_: SecurityException) {
            } catch (_: UnsupportedOperationException) {
            }
        }
    }

    private fun updateTransfer(item: TransferItem) {
        _transfers.update { list ->
            val index = list.indexOfFirst { it.id == item.id }
            if (index < 0) {
                list + item
            } else {
                list.toMutableList().also { it[index] = item }
            }
        }
    }

    override fun onCleared() {
        discoveryManager.stopDiscovery()
        connection?.close()
        super.onCleared()
    }
}
