package com.phonelink.android

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import com.phonelink.android.ui.AppViewModel
import com.phonelink.android.ui.HomeScreen
import com.phonelink.android.ui.TransferScreen
import com.phonelink.android.ui.theme.PhoneLinkTheme

class MainActivity : ComponentActivity() {

    private val viewModel: AppViewModel by viewModels()

    private val openDocuments = registerForActivityResult(
        ActivityResultContracts.OpenMultipleDocuments(),
    ) { uris: List<Uri>? ->
        if (!uris.isNullOrEmpty()) {
            viewModel.sendFiles(uris)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleShareIntent(intent)
        setContent {
            PhoneLinkTheme {
                var showTransfers by rememberSaveable { mutableStateOf(false) }

                if (showTransfers) {
                    TransferScreen(
                        viewModel = viewModel,
                        onBack = { showTransfers = false },
                        onPickFiles = { openDocuments.launch(arrayOf("*/*")) },
                    )
                } else {
                    HomeScreen(
                        viewModel = viewModel,
                        onOpenTransfers = { showTransfers = true },
                        onShowPending = { showTransfers = true },
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleShareIntent(intent)
    }

    private fun handleShareIntent(intent: Intent?) {
        if (intent == null) return
        when (intent.action) {
            Intent.ACTION_SEND -> {
                val uri = if (android.os.Build.VERSION.SDK_INT >= 33) {
                    intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableExtra(Intent.EXTRA_STREAM)
                }
                if (uri != null) {
                    viewModel.queueIncomingShare(listOf(uri))
                }
            }
            Intent.ACTION_SEND_MULTIPLE -> {
                val uris = if (android.os.Build.VERSION.SDK_INT >= 33) {
                    intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM)
                }
                if (!uris.isNullOrEmpty()) {
                    viewModel.queueIncomingShare(uris)
                }
            }
        }
    }
}
