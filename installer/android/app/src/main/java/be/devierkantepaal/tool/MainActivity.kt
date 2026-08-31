package be.devierkantepaal.tool

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
import android.view.KeyEvent
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.net.Socket
import kotlin.concurrent.thread

class MainActivity : Activity() {

    private var web: WebView? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val wachtscherm = TextView(this).apply {
            text = "De Vierkante Paal wordt gestart…"
            textSize = 18f
            setPadding(48, 96, 48, 48)
        }
        setContentView(wachtscherm)

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        val py = Python.getInstance()
        val port = py.getModule("android_start")
            .callAttr("start", filesDir.absolutePath)
            .toInt()

        thread {
            var op = false
            repeat(150) {
                try {
                    Socket("127.0.0.1", port).close()
                    op = true
                    return@repeat
                } catch (e: Exception) {
                    Thread.sleep(100)
                }
            }
            runOnUiThread {
                if (!op) {
                    wachtscherm.text =
                        "De server is niet opgestart. Zie logcat (tag: python.stderr)."
                    return@runOnUiThread
                }
                val w = WebView(this)
                web = w
                w.settings.javaScriptEnabled = true
                w.settings.domStorageEnabled = true
                w.settings.databaseEnabled = true
                // Zonder eigen WebViewClient geeft de WebView elke navigatie
                // (ook location.reload()) door aan het systeem -> externe browser.
                w.webViewClient = WebViewClient()
                setContentView(w)
                w.loadUrl("http://127.0.0.1:$port/")
            }
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        val w = web
        if (keyCode == KeyEvent.KEYCODE_BACK && w != null && w.canGoBack()) {
            w.goBack()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }
}
