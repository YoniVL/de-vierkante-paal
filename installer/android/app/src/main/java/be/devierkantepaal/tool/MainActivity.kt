package be.devierkantepaal.tool

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
import android.webkit.WebView
import android.widget.TextView
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.net.Socket
import kotlin.concurrent.thread

class MainActivity : Activity() {

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

        // De Python-server starten; die geeft de poort terug.
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
                    wachtscherm.text = "De server is niet opgestart. Zie logcat (tag: python.stderr)."
                    return@runOnUiThread
                }
                val web = WebView(this)
                web.settings.javaScriptEnabled = true
                web.settings.domStorageEnabled = true
                web.settings.databaseEnabled = true
                setContentView(web)
                web.loadUrl("http://127.0.0.1:$port/")
            }
        }
    }
}
