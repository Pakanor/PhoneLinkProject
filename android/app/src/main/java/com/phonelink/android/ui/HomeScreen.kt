package com.phonelink.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.phonelink.android.discovery.DiscoveredServer
import com.phonelink.android.network.ConnectionState

@Composable
fun HomeScreen(
    viewModel: AppViewModel,
    onOpenTransfers: () -> Unit,
    onShowPending: () -> Unit,
) {
    val connectionState by viewModel.connectionState.collectAsState()
    val scanning by viewModel.scanning.collectAsState()
    val servers by viewModel.servers.collectAsState()
    val pendingCount by viewModel.pendingShareUris.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        Text(
            text = "PhoneLink",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(8.dp))

        ConnectionBadge(connectionState)

        Spacer(Modifier.height(12.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Button(
                onClick = { viewModel.scanNetwork() },
                modifier = Modifier.weight(1f),
            ) {
                Text(if (scanning) "Skanowanie…" else "Skanuj sieć")
            }
            if (connectionState == ConnectionState.CONNECTED) {
                OutlinedButton(onClick = { viewModel.disconnect() }) {
                    Text("Rozłącz")
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        Text(
            text = "Wykryte komputery",
            style = MaterialTheme.typography.titleMedium,
        )
        Spacer(Modifier.height(4.dp))

        if (servers.isEmpty()) {
            Text(
                text = "Brak wykrytych serwerów. Uruchom serwer PhoneLink na komputerze i naciśnij „Skanuj sieć”.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        LazyColumn {
            items(servers, key = { it.name }) { server ->
                ServerCard(
                    server = server,
                    enabled = connectionState != ConnectionState.CONNECTING,
                    onConnect = { viewModel.connectTo(server) },
                )
            }
        }

        Spacer(Modifier.weight(1f))

        if (pendingCount > 0) {
            Card(modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Text(
                        text = "Udostępniono $pendingCount plik(ów) do wysłania",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    TextButton(onClick = onShowPending) {
                        Text("Przejdź do panelu transferu")
                    }
                }
            }
        }

        OutlinedButton(
            onClick = onOpenTransfers,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Panel transferu")
        }
    }
}

@Composable
private fun ConnectionBadge(state: ConnectionState) {
    val (label, color) = when (state) {
        ConnectionState.DISCONNECTED -> "Rozłączony" to Color(0xFF9E9E9E)
        ConnectionState.DISCOVERING -> "Skanowanie…" to Color(0xFFFFA000)
        ConnectionState.CONNECTING -> "Łączenie…" to Color(0xFFFFA000)
        ConnectionState.CONNECTED -> "Połączono szyfrowaniem ECDH" to Color(0xFF4CAF50)
    }
    Surface(
        color = color.copy(alpha = 0.15f),
        shape = MaterialTheme.shapes.small,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            text = label,
            color = color,
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
        )
    }
}

@Composable
private fun ServerCard(
    server: DiscoveredServer,
    enabled: Boolean,
    onConnect: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    text = server.name.ifEmpty { "Serwer PhoneLink" },
                    style = MaterialTheme.typography.titleSmall,
                )
                Text(
                    text = "${server.host}:${server.port}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Button(onClick = onConnect, enabled = enabled) {
                Text("Połącz")
            }
        }
    }
}
