package com.phonelink.android.discovery

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Wykryty serwer PhoneLink w sieci lokalnej. */
data class DiscoveredServer(
    val name: String,
    val host: String,
    val port: Int,
)

/**
 * Skanowanie sieci lokalnej przez NsdManager (mDNS) w poszukiwaniu
 * usługi `_phonelink._tcp.local.` (typ dla NsdManager: "_phonelink._tcp.").
 */
class NsdDiscoveryManager(context: Context) {

    companion object {
        const val SERVICE_TYPE = "_phonelink._tcp."
    }

    private val appContext = context.applicationContext
    private val nsdManager: NsdManager =
        appContext.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifiManager: WifiManager =
        appContext.getSystemService(Context.WIFI_SERVICE) as WifiManager

    private var multicastLock: WifiManager.MulticastLock? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null

    private val _servers = MutableStateFlow<List<DiscoveredServer>>(emptyList())
    val servers: StateFlow<List<DiscoveredServer>> = _servers.asStateFlow()

    private val _scanning = MutableStateFlow(false)
    val scanning: StateFlow<Boolean> = _scanning.asStateFlow()

    @Volatile
    private var discovering = false

    fun isDiscovering(): Boolean = discovering

    fun startDiscovery() {
        if (discovering) return
        _servers.value = emptyList()
        discovering = true
        _scanning.value = true

        multicastLock = wifiManager.createMulticastLock("phonelink-nsd").apply {
            setReferenceCounted(false)
            acquire()
        }

        val listener = object : NsdManager.DiscoveryListener {
            override fun onServiceFound(serviceType: String, serviceInfo: NsdServiceInfo) {
                if (serviceType.contains("_phonelink._tcp")) {
                    resolveService(serviceInfo)
                }
            }

            override fun onServiceLost(serviceType: String, serviceInfo: NsdServiceInfo) {
                _servers.value = _servers.value.filterNot { it.name == serviceInfo.serviceName }
            }

            override fun onDiscoveryStarted(serviceType: String) = Unit

            override fun onDiscoveryStopped(serviceType: String) {
                discovering = false
                _scanning.value = false
                releaseLock()
            }

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                discovering = false
                _scanning.value = false
                releaseLock()
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                releaseLock()
            }
        }

        discoveryListener = listener
        nsdManager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
    }

    fun stopDiscovery() {
        discoveryListener?.let { listener ->
            runCatching { nsdManager.stopServiceDiscovery(listener) }
        }
        discoveryListener = null
        discovering = false
        _scanning.value = false
        releaseLock()
    }

    private fun resolveService(serviceInfo: NsdServiceInfo) {
        nsdManager.resolveService(serviceInfo, object : NsdManager.ResolveListener {
            override fun onResolved(info: NsdServiceInfo) {
                val host = info.host?.hostAddress ?: return
                val server = DiscoveredServer(info.serviceName, host, info.port)
                val current = _servers.value
                if (current.none { it.name == server.name }) {
                    _servers.value = current + server
                }
            }

            override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) = Unit
        })
    }

    private fun releaseLock() {
        multicastLock?.let { lock ->
            if (lock.isHeld) {
                lock.release()
            }
        }
        multicastLock = null
    }
}
