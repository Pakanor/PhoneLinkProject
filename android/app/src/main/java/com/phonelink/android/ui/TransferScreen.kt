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
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.phonelink.android.network.ConnectionState
import com.phonelink.android.network.TransferItem
import com.phonelink.android.network.TransferState

@Composable
fun TransferScreen(
    viewModel: AppViewModel,
    onBack: () -> Unit,
    onPickFiles: () -> Unit,
) {
    val transfers by viewModel.transfers.collectAsState()
    val pending by viewModel.pendingShareUris.collectAsState()
    val connectionState by viewModel.connectionState.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("← Wróć") }
            Spacer(Modifier.weight(1f))
            Button(onClick = onPickFiles) {
                Text("Wybierz pliki")
            }
        }

        if (pending.isNotEmpty()) {
            Card(modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Text(
                        text = "Pliki z „Udostępnij”: ${pending.size}",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    if (connectionState == ConnectionState.CONNECTED) {
                        Button(
                            onClick = { viewModel.sendPendingShares() },
                            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                        ) {
                            Text("Wyślij teraz")
                        }
                    } else {
                        Text(
                            text = "Połącz się z komputerem, aby wysłać",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }

        Text(
            text = "Transfery",
            style = MaterialTheme.typography.titleMedium,
        )
        Spacer(Modifier.height(4.dp))

        if (transfers.isEmpty()) {
            Text(
                text = "Brak transferów. Wybierz pliki lub odeślij je z komputera.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        LazyColumn {
            items(transfers, key = { it.id }) { item ->
                TransferCard(item)
            }
        }
    }
}

@Composable
private fun TransferCard(item: TransferItem) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = item.fileName,
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = item.direction.label,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Spacer(Modifier.height(6.dp))

            LinearProgressIndicator(
                progress = { item.fraction },
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(6.dp))

            Row(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "${item.percent}%  •  ${"%.2f".format(item.speedMbps)} MB/s",
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.weight(1f),
                )
                StatusLabel(item)
            }
        }
    }
}

@Composable
private fun StatusLabel(item: TransferItem) {
    when (item.state) {
        TransferState.RUNNING -> Text(
            text = "w toku",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary,
        )
        TransferState.DONE -> Text(
            text = if (item.sha256Ok == true) "SHA-256 OK" else "zakończono",
            style = MaterialTheme.typography.labelMedium,
            color = Color(0xFF4CAF50),
        )
        TransferState.FAILED -> Text(
            text = "błąd: ${item.error ?: "nieznany"}",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.error,
        )
    }
}
