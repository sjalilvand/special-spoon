package ir.rosedoctor.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.view.Window;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

/**
 * فاز ۶۸ - پوستهٔ آنلاین سایت رز دکتر (به‌روز فاز ۹۴: تلاش اول روی دامنهٔ اصلی).
 * اپ هیچ داده‌ای را نگه نمی‌دارد؛ همه‌چیز از خود سایت خوانده می‌شود:
 * فاز ۹۴ — دامنهٔ rosedoctor.ir ست شده و TCP 80 باز است؛ پس ترتیب تلاش:
 * ۱) http://rosedoctor.ir/ (پورت ۸۰، آدرس رسمی) ← ۲) همان دامنه روی ۸۰۸۰
 * ← ۳) IP خام روی ۸۰۸۰ (بدون DNS) ← ۴) https (وقتی گواهی فعال شد).
 * صفحهٔ خطا هم دکمهٔ «تلاش دوباره» دارد که از دامنه شروع می‌کند.
 */
public class MainActivity extends Activity {

    private static final String SERVER_IP = "130.185.73.157";
    private static final String HOST = "rosedoctor.ir"; // فاز ۸۷ — دامنهٔ اصلی
    // فاز ۹۴ — آدرس رسمی اول، سپس ۸۰۸۰، سپس IP خام و در آخر https
    private static final String START_FAST  = "http://" + HOST + "/";
    private static final String START_ALT   = "http://" + HOST + ":8080/";
    private static final String START_IP    = "http://" + SERVER_IP + ":8080/";
    private static final String START_HTTPS = "https://" + HOST + "/";

    private static final int FILE_CHOOSER_CODE = 4242;

    private WebView web;
    private ProgressBar progress;
    private LinearLayout errorBox;
    private int attempt = 0; // ۰=دامنه:۸۰ (رسمی) ، ۱=دامنه:۸۰۸۰ ، ۲=IP:۸۰۸۰ ، ۳=https
    private ValueCallback<Uri[]> pendingFilePick;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window w = getWindow();
        w.setStatusBarColor(Color.parseColor("#7c2740"));

        setContentView(R.layout.activity_main);
        web = findViewById(R.id.web);
        progress = findViewById(R.id.progress);
        errorBox = findViewById(R.id.errorBox);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setSupportZoom(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);

        CookieManager ck = CookieManager.getInstance();
        ck.setAcceptCookie(true);
        ck.setAcceptThirdPartyCookies(web, true);
        ck.flush();

        web.setWebViewClient(new RoseClient());
        web.setWebChromeClient(new RoseChrome());
        web.setDownloadListener(new RoseDownloader());

        findViewById(R.id.retryBtn).setOnClickListener(v -> {
            attempt = 0; // تلاش دوباره همیشه از آدرس رسمی دامنه شروع می‌کند
            loadSite();
        });

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            loadSite();
        }
    }

    private String startUrl(int a) {
        if (a <= 0) return START_FAST;
        if (a == 1) return START_ALT;
        if (a == 2) return START_IP;
        if (a == 3) return START_HTTPS;
        return START_FAST;
    }

    private void loadSite() {
        hideError();
        web.loadUrl(startUrl(attempt));
    }

    private void showError() {
        progress.setVisibility(View.GONE);
        errorBox.setVisibility(View.VISIBLE);
    }

    private void hideError() {
        errorBox.setVisibility(View.GONE);
    }

    /**
     * خرابی صفحهٔ اصلی: دامنه:۸۰ ← دامنه:۸۰۸۰ ← IP:۸۰۸۰ ← HTTPS و بعد صفحهٔ خطا با دکمهٔ تلاش دوباره.
     */
    private void handleMainFailure() {
        if (attempt < 3) {
            attempt++;
            web.loadUrl(startUrl(attempt));
        } else {
            showError();
        }
    }

    private class RoseClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
            Uri u = req.getUrl();
            String scheme = u.getScheme() == null ? "" : u.getScheme();
            if (scheme.equals("http") || scheme.equals("https")) {
                return false; // همهٔ صفحات سایت داخل همان اپ باز می‌شوند
            }
            // tel: / mailto: / sms: / intent: و...
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, u));
            } catch (ActivityNotFoundException e) {
                Toast.makeText(MainActivity.this, R.string.cannot_open, Toast.LENGTH_SHORT).show();
            }
            return true;
        }

        @Override
        public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
            if (req.isForMainFrame()) {
                handleMainFailure();
            }
        }

        @Override
        public void onReceivedSslError(WebView v, SslErrorHandler handler,
                                       android.net.http.SslError error) {
            // تا وقتی گواهی HTTPS روی سرور فعال نشده، گواهی معتبر جواب نمی‌دهد؛
            // ادامه به تلاش بعدی (IP:۸۰۸۰ یا صفحهٔ خطا).
            handler.cancel();
            if (v.getUrl() != null && v.getUrl().startsWith("https://")) {
                handleMainFailure();
            }
        }

        @Override
        public void onPageFinished(WebView v, String url) {
            progress.setVisibility(View.GONE);
            if (!url.startsWith("http")) {
                return;
            }
            hideError();
        }
    }

    private class RoseChrome extends WebChromeClient {
        @Override
        public void onProgressChanged(WebView v, int newProgress) {
            if (newProgress < 100) {
                progress.setVisibility(View.VISIBLE);
                progress.setProgress(newProgress);
            } else {
                progress.setVisibility(View.GONE);
            }
        }

        @Override
        public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> callback,
                                         FileChooserParams params) {
            if (pendingFilePick != null) {
                pendingFilePick.onReceiveValue(null);
            }
            pendingFilePick = callback;
            try {
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                startActivityForResult(
                        Intent.createChooser(i, getString(R.string.pick_file)), FILE_CHOOSER_CODE);
            } catch (ActivityNotFoundException e) {
                pendingFilePick = null;
                return false;
            }
            return true;
        }
    }

    /** دانلود فایل‌ها (مانند خروجی‌های پنل) با DownloadManager سیستم. */
    private class RoseDownloader implements android.webkit.DownloadListener {
        @Override
        public void onDownloadStart(String url, String ua, String cd, String mime, long size) {
            try {
                String name = "rosedoctor-download";
                if (cd != null && cd.contains("filename=")) {
                    int i = cd.indexOf("filename=") + 9;
                    name = cd.substring(i).replace("\"", "").trim();
                } else {
                    int q = url.lastIndexOf('/');
                    if (q >= 0 && q < url.length() - 1) {
                        name = url.substring(q + 1);
                    }
                }
                DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
                r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
                DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                dm.enqueue(r);
                Toast.makeText(MainActivity.this, R.string.download_started, Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                } catch (ActivityNotFoundException ignored) {
                }
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER_CODE && pendingFilePick != null) {
            pendingFilePick.onReceiveValue(
                    WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            pendingFilePick = null;
        } else {
            super.onActivityResult(requestCode, resultCode, data);
        }
    }

    @Override
    public void onBackPressed() {
        // ناوبری SPA سایت با دکمهٔ برگشت اندروید
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
        web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }
}
