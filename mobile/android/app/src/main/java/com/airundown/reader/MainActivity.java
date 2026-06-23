package com.airundown.reader;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private static final String PREFS = "ai_rundown_reader";
    private static final String KEY_BASE_URL = "base_url";
    private static final String KEY_TOKEN = "token";
    private static final String KEY_SUPABASE_URL = "supabase_url";
    private static final String KEY_SUPABASE_ANON_KEY = "supabase_anon_key";
    private static final String KEY_ARTICLES = "cache_articles";
    private static final String KEY_VOCAB = "local_vocab";

    private final int bg = 0xFFF7F7F2;
    private final int ink = 0xFF202124;
    private final int muted = 0xFF5F6368;
    private final int line = 0xFFE0E0D8;
    private final int card = 0xFFFFFFFF;
    private final int accent = 0xFF176B87;
    private final int warm = 0xFFB85C38;
    private final int soft = 0xFFE7F0EF;

    private SharedPreferences prefs;
    private LinearLayout root;
    private EditText urlInput;
    private EditText tokenInput;
    private EditText supabaseUrlInput;
    private EditText supabaseKeyInput;
    private ProgressBar progress;
    private JSONArray cachedArticles = new JSONArray();
    private JSONObject currentArticle;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        try {
            cachedArticles = new JSONArray(prefs.getString(KEY_ARTICLES, "[]"));
        } catch (JSONException ignored) {
            cachedArticles = new JSONArray();
        }
        buildShell();
        renderHome();
        refreshArticles(false);
    }

    private void buildShell() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(bg);
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(20), dp(18), dp(28));
        scroll.addView(root, new ScrollView.LayoutParams(-1, -2));
        setContentView(scroll);
    }

    private void renderHome() {
        currentArticle = null;
        root.removeAllViews();
        addHeader();
        addConnectionPanel();
        addActionBar();
        addSectionTitle("Articles");
        if (cachedArticles.length() == 0) {
            TextView empty = body("No articles yet. Start the backend, then tap Sync or Sample.");
            empty.setTextColor(muted);
            root.addView(empty);
        } else {
            for (int i = 0; i < cachedArticles.length(); i++) {
                JSONObject item = cachedArticles.optJSONObject(i);
                if (item != null) {
                    addArticleRow(item);
                }
            }
        }
        addSectionTitle("Saved Vocabulary");
        addVocabPanel();
    }

    private void addHeader() {
        TextView title = new TextView(this);
        title.setText("AI Rundown");
        title.setTextColor(ink);
        title.setTextSize(28);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setIncludeFontPadding(false);
        root.addView(title);

        TextView subtitle = body("Read first, reveal chunks, save useful words.");
        subtitle.setTextColor(muted);
        subtitle.setPadding(0, dp(6), 0, dp(18));
        root.addView(subtitle);
    }

    private void addConnectionPanel() {
        LinearLayout panel = panel();

        TextView label = smallLabel("Backend URL");
        panel.addView(label);
        urlInput = input("http://192.168.0.12:8787");
        urlInput.setText(prefs.getString(KEY_BASE_URL, ""));
        panel.addView(urlInput);

        TextView tokenLabel = smallLabel("App token");
        tokenLabel.setPadding(0, dp(10), 0, dp(4));
        panel.addView(tokenLabel);
        tokenInput = input("change-me");
        tokenInput.setText(prefs.getString(KEY_TOKEN, ""));
        tokenInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        panel.addView(tokenInput);

        TextView supabaseUrlLabel = smallLabel("Supabase URL");
        supabaseUrlLabel.setPadding(0, dp(10), 0, dp(4));
        panel.addView(supabaseUrlLabel);
        supabaseUrlInput = input("https://your-project-ref.supabase.co");
        supabaseUrlInput.setText(prefs.getString(KEY_SUPABASE_URL, ""));
        panel.addView(supabaseUrlInput);

        TextView supabaseKeyLabel = smallLabel("Supabase anon key");
        supabaseKeyLabel.setPadding(0, dp(10), 0, dp(4));
        panel.addView(supabaseKeyLabel);
        supabaseKeyInput = input("anon or publishable key");
        supabaseKeyInput.setText(prefs.getString(KEY_SUPABASE_ANON_KEY, ""));
        supabaseKeyInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        panel.addView(supabaseKeyInput);

        Button save = button("Save Settings", accent);
        save.setOnClickListener(v -> {
            prefs.edit()
                    .putString(KEY_BASE_URL, cleanBaseUrl())
                    .putString(KEY_TOKEN, tokenInput.getText().toString().trim())
                    .putString(KEY_SUPABASE_URL, cleanSupabaseUrl())
                    .putString(KEY_SUPABASE_ANON_KEY, cleanSupabaseAnonKey())
                    .apply();
            toast("Saved");
        });
        panel.addView(save);

        root.addView(panel);
    }

    private void addActionBar() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(0, dp(12), 0, dp(8));

        Button refresh = button("Refresh", accent);
        refresh.setOnClickListener(v -> refreshArticles(true));
        row.addView(refresh, weightParams());

        Button sync = button("Sync", warm);
        sync.setOnClickListener(v -> syncMail());
        LinearLayout.LayoutParams second = weightParams();
        second.setMargins(dp(8), 0, 0, 0);
        row.addView(sync, second);

        Button sample = button("Sample", 0xFF4F6F52);
        sample.setOnClickListener(v -> createSample());
        LinearLayout.LayoutParams third = weightParams();
        third.setMargins(dp(8), 0, 0, 0);
        row.addView(sample, third);

        root.addView(row);
        progress = new ProgressBar(this);
        progress.setVisibility(View.GONE);
        root.addView(progress);
    }

    private void addArticleRow(JSONObject item) {
        LinearLayout box = panel();
        box.setOnClickListener(v -> openArticle(item.optInt("id")));

        TextView title = new TextView(this);
        title.setText(item.optString("subject", "Untitled"));
        title.setTextColor(ink);
        title.setTextSize(17);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        box.addView(title);

        TextView meta = body(item.optString("received_at", "") + "  |  " + item.optString("status", ""));
        meta.setTextColor(muted);
        meta.setPadding(0, dp(6), 0, 0);
        box.addView(meta);

        root.addView(box);
    }

    private void renderArticle(JSONObject article) {
        currentArticle = article;
        root.removeAllViews();

        Button back = button("Back", accent);
        back.setOnClickListener(v -> renderHome());
        root.addView(back);

        TextView title = new TextView(this);
        title.setText(article.optString("subject", "Untitled"));
        title.setTextColor(ink);
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, dp(16), 0, dp(8));
        root.addView(title);

        TextView meta = body(article.optString("received_at", ""));
        meta.setTextColor(muted);
        root.addView(meta);

        String html = article.optString("html", "");
        if (!html.trim().isEmpty()) {
            Button original = button("Original Email", 0xFF4F6F52);
            original.setOnClickListener(v -> renderOriginalEmail(article));
            root.addView(original);
        }

        JSONArray sections = article.optJSONArray("sections");
        if (sections == null || sections.length() == 0) {
            TextView empty = body("This article has no analysis yet. Tap Re-analyze.");
            empty.setTextColor(muted);
            empty.setPadding(0, dp(16), 0, dp(8));
            root.addView(empty);
        } else {
            for (int i = 0; i < sections.length(); i++) {
                JSONObject section = sections.optJSONObject(i);
                if (section != null) {
                    addSection(section);
                }
            }
        }

        Button reanalyze = button("Re-analyze", warm);
        reanalyze.setOnClickListener(v -> reanalyze(article.optInt("id")));
        root.addView(reanalyze);
    }

    private void renderOriginalEmail(JSONObject article) {
        root.removeAllViews();

        Button back = button("Back to Analysis", accent);
        back.setOnClickListener(v -> renderArticle(article));
        root.addView(back);

        TextView title = new TextView(this);
        title.setText(article.optString("subject", "Original Email"));
        title.setTextColor(ink);
        title.setTextSize(22);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, dp(16), 0, dp(12));
        root.addView(title);

        WebView webView = new WebView(this);
        webView.setWebViewClient(new WebViewClient());
        webView.getSettings().setJavaScriptEnabled(false);
        webView.getSettings().setLoadWithOverviewMode(true);
        webView.getSettings().setUseWideViewPort(true);
        webView.getSettings().setBuiltInZoomControls(true);
        webView.getSettings().setDisplayZoomControls(false);
        webView.setBackgroundColor(0xFFFFFFFF);

        String html = article.optString("html", "");
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(900));
        params.setMargins(0, dp(8), 0, dp(12));
        root.addView(webView, params);
    }

    private void addSection(JSONObject section) {
        addSectionTitle(section.optString("heading", "Section"));
        JSONArray sentences = section.optJSONArray("sentences");
        if (sentences == null || sentences.length() == 0) {
            TextView body = body(section.optString("body", ""));
            body.setTextColor(ink);
            root.addView(body);
            return;
        }
        for (int i = 0; i < sentences.length(); i++) {
            JSONObject sentence = sentences.optJSONObject(i);
            if (sentence != null) {
                addSentenceCard(sentence);
            }
        }
    }

    private void addSentenceCard(JSONObject sentence) {
        LinearLayout box = panel();

        TextView original = body(sentence.optString("source_text", ""));
        original.setTextColor(ink);
        original.setTextSize(17);
        box.addView(original);

        LinearLayout reveal = new LinearLayout(this);
        reveal.setOrientation(LinearLayout.VERTICAL);
        reveal.setVisibility(View.GONE);

        TextView translation = body("-> " + sentence.optString("translation", ""));
        translation.setTextColor(accent);
        translation.setTypeface(Typeface.DEFAULT_BOLD);
        translation.setPadding(0, dp(10), 0, dp(8));
        reveal.addView(translation);

        JSONArray chunks = sentence.optJSONArray("chunks");
        if (chunks != null) {
            for (int i = 0; i < chunks.length(); i++) {
                JSONObject chunk = chunks.optJSONObject(i);
                if (chunk != null) {
                    TextView chunkText = body("- " + chunk.optString("text") + " : " + chunk.optString("meaning"));
                    chunkText.setTextColor(ink);
                    reveal.addView(chunkText);
                    String note = chunk.optString("note", "");
                    if (!note.isEmpty()) {
                        TextView noteText = body("  " + note);
                        noteText.setTextColor(muted);
                        reveal.addView(noteText);
                    }
                }
            }
        }

        JSONArray vocabulary = sentence.optJSONArray("vocabulary");
        if (vocabulary != null && vocabulary.length() > 0) {
            TextView vocabTitle = smallLabel("Vocabulary");
            vocabTitle.setPadding(0, dp(10), 0, dp(4));
            reveal.addView(vocabTitle);
            for (int i = 0; i < vocabulary.length(); i++) {
                JSONObject vocab = vocabulary.optJSONObject(i);
                if (vocab != null) {
                    addVocabCandidate(reveal, sentence, vocab);
                }
            }
        }

        Button toggle = button("Reveal", accent);
        toggle.setOnClickListener(v -> {
            boolean hidden = reveal.getVisibility() == View.GONE;
            reveal.setVisibility(hidden ? View.VISIBLE : View.GONE);
            toggle.setText(hidden ? "Hide" : "Reveal");
        });
        box.addView(toggle);
        box.addView(reveal);
        root.addView(box);
    }

    private void addVocabCandidate(LinearLayout parent, JSONObject sentence, JSONObject vocab) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.VERTICAL);
        row.setPadding(0, dp(6), 0, dp(8));

        String term = vocab.optString("term", "");
        String meaning = vocab.optString("meaning", "");
        TextView word = body(term + "  -  " + meaning);
        word.setTextColor(ink);
        row.addView(word);

        Button save = button("Save Word", 0xFF4F6F52);
        save.setOnClickListener(v -> saveVocab(
                currentArticle == null ? 0 : currentArticle.optInt("id"),
                sentence.optInt("id"),
                term,
                meaning,
                ""
        ));
        row.addView(save);
        parent.addView(row);
    }

    private void addVocabPanel() {
        JSONArray vocab = getLocalVocab();
        if (vocab.length() == 0) {
            TextView empty = body("No saved words yet.");
            empty.setTextColor(muted);
            root.addView(empty);
            return;
        }
        for (int i = 0; i < vocab.length(); i++) {
            JSONObject item = vocab.optJSONObject(i);
            if (item == null) continue;
            TextView line = body(item.optString("term") + "  -  " + item.optString("meaning"));
            line.setTextColor(ink);
            root.addView(line);
        }
        Button share = button("Share TSV", accent);
        share.setOnClickListener(v -> shareTsv());
        root.addView(share);
        Button copy = button("Copy TSV", warm);
        copy.setOnClickListener(v -> copyTsv());
        root.addView(copy);
    }

    private void refreshArticles(boolean loud) {
        if (hasSupabase()) {
            refreshSupabaseArticles(loud);
            return;
        }
        request("GET", "/api/articles", null, new ApiCallback() {
            @Override
            public void ok(JSONObject json) {
                cachedArticles = json.optJSONArray("articles");
                if (cachedArticles == null) cachedArticles = new JSONArray();
                prefs.edit().putString(KEY_ARTICLES, cachedArticles.toString()).apply();
                renderHome();
                if (loud) toast("Refreshed");
            }

            @Override
            public void fail(String message) {
                if (loud) toast(message);
            }
        });
    }

    private void openArticle(int id) {
        if (hasSupabase()) {
            openSupabaseArticle(id);
            return;
        }
        request("GET", "/api/articles/" + id, null, new ApiCallback() {
            @Override
            public void ok(JSONObject json) {
                prefs.edit().putString("cache_article_" + id, json.toString()).apply();
                renderArticle(json);
            }

            @Override
            public void fail(String message) {
                String cached = prefs.getString("cache_article_" + id, "");
                if (!cached.isEmpty()) {
                    try {
                        renderArticle(new JSONObject(cached));
                        toast("Showing cached article");
                    } catch (JSONException e) {
                        toast(message);
                    }
                } else {
                    toast(message);
                }
            }
        });
    }

    private void syncMail() {
        request("POST", "/api/sync", "{}", new ApiCallback() {
            @Override
            public void ok(JSONObject json) {
                toast("Sync complete");
                refreshArticles(false);
            }

            @Override
            public void fail(String message) {
                toast(message);
            }
        });
    }

    private void createSample() {
        request("POST", "/api/sample", "{}", new ApiCallback() {
            @Override
            public void ok(JSONObject json) {
                toast("Sample created");
                refreshArticles(false);
            }

            @Override
            public void fail(String message) {
                toast(message);
            }
        });
    }

    private void reanalyze(int articleId) {
        request("POST", "/api/articles/" + articleId + "/reanalyze", "{}", new ApiCallback() {
            @Override
            public void ok(JSONObject json) {
                toast("Analysis refreshed");
                openArticle(articleId);
            }

            @Override
            public void fail(String message) {
                toast(message);
            }
        });
    }

    private void saveVocab(int articleId, int sentenceId, String term, String meaning, String note) {
        JSONArray vocab = getLocalVocab();
        for (int i = 0; i < vocab.length(); i++) {
            JSONObject existing = vocab.optJSONObject(i);
            if (existing != null && term.equalsIgnoreCase(existing.optString("term"))) {
                toast("Already saved");
                return;
            }
        }
        JSONObject item = new JSONObject();
        try {
            item.put("article_id", articleId);
            item.put("sentence_id", sentenceId);
            item.put("term", term);
            item.put("meaning", meaning);
            item.put("note", note);
            vocab.put(item);
            prefs.edit().putString(KEY_VOCAB, vocab.toString()).apply();
        } catch (JSONException ignored) {
        }
        JSONObject body = new JSONObject();
        try {
            body.put("article_id", articleId);
            body.put("sentence_id", sentenceId);
            body.put("term", term);
            body.put("meaning", meaning);
            body.put("note", note);
            if (hasSupabase()) {
                saveVocabToSupabase(body.toString());
            } else {
                request("POST", "/api/vocab", body.toString(), new ApiCallback() {
                    @Override public void ok(JSONObject json) { }
                    @Override public void fail(String message) { }
                });
            }
        } catch (JSONException ignored) {
        }
        toast("Saved");
    }

    private void refreshSupabaseArticles(boolean loud) {
        setBusy(true);
        new Thread(() -> {
            try {
                JSONArray articles = supabaseArray(
                        "GET",
                        "/rest/v1/articles?select=id,uid,subject,sender,received_at,status,error,created_at,updated_at&order=received_at.desc&limit=50",
                        null
                );
                runOnUiThread(() -> {
                    setBusy(false);
                    cachedArticles = articles;
                    prefs.edit().putString(KEY_ARTICLES, cachedArticles.toString()).apply();
                    renderHome();
                    if (loud) toast("Refreshed from Supabase");
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    setBusy(false);
                    if (loud) toast(e.getMessage() == null ? "Supabase refresh failed" : e.getMessage());
                });
            }
        }).start();
    }

    private void openSupabaseArticle(int id) {
        setBusy(true);
        new Thread(() -> {
            try {
                JSONArray articleRows = supabaseArray("GET", "/rest/v1/articles?id=eq." + id + "&select=*", null);
                if (articleRows.length() == 0) {
                    throw new IllegalStateException("Article not found");
                }
                JSONObject article = articleRows.getJSONObject(0);
                JSONArray sections = supabaseArray(
                        "GET",
                        "/rest/v1/sections?article_id=eq." + id + "&select=*&order=ordinal.asc",
                        null
                );
                JSONArray sentences = supabaseArray(
                        "GET",
                        "/rest/v1/sentences?article_id=eq." + id + "&select=*&order=section_id.asc,ordinal.asc",
                        null
                );
                for (int i = 0; i < sections.length(); i++) {
                    JSONObject section = sections.getJSONObject(i);
                    long sectionId = section.optLong("id");
                    JSONArray sectionSentences = new JSONArray();
                    for (int j = 0; j < sentences.length(); j++) {
                        JSONObject sentence = sentences.getJSONObject(j);
                        if (sentence.optLong("section_id") == sectionId) {
                            sectionSentences.put(sentence);
                        }
                    }
                    section.put("sentences", sectionSentences);
                }
                article.put("sections", sections);
                runOnUiThread(() -> {
                    setBusy(false);
                    prefs.edit().putString("cache_article_" + id, article.toString()).apply();
                    renderArticle(article);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    setBusy(false);
                    String cached = prefs.getString("cache_article_" + id, "");
                    if (!cached.isEmpty()) {
                        try {
                            renderArticle(new JSONObject(cached));
                            toast("Showing cached article");
                        } catch (JSONException ignored) {
                            toast(e.getMessage() == null ? "Supabase article failed" : e.getMessage());
                        }
                    } else {
                        toast(e.getMessage() == null ? "Supabase article failed" : e.getMessage());
                    }
                });
            }
        }).start();
    }

    private void saveVocabToSupabase(String body) {
        new Thread(() -> {
            try {
                supabaseRaw("POST", "/rest/v1/vocab", body, true);
            } catch (Exception ignored) {
            }
        }).start();
    }

    private JSONArray getLocalVocab() {
        try {
            return new JSONArray(prefs.getString(KEY_VOCAB, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }

    private String vocabTsv() {
        JSONArray vocab = getLocalVocab();
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < vocab.length(); i++) {
            JSONObject item = vocab.optJSONObject(i);
            if (item == null) continue;
            builder.append(cleanCell(item.optString("term")))
                    .append('\t')
                    .append(cleanCell(item.optString("meaning")));
            String note = item.optString("note", "");
            if (!note.isEmpty()) {
                builder.append(" (").append(cleanCell(note)).append(")");
            }
            builder.append('\n');
        }
        return builder.toString();
    }

    private void shareTsv() {
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_TEXT, vocabTsv());
        startActivity(Intent.createChooser(send, "Share Anki TSV"));
    }

    private void copyTsv() {
        ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        clipboard.setPrimaryClip(ClipData.newPlainText("anki.tsv", vocabTsv()));
        toast("Copied TSV");
    }

    private String cleanCell(String value) {
        return value.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').trim();
    }

    private void request(String method, String path, String body, ApiCallback callback) {
        String base = cleanBaseUrl();
        if (base.isEmpty()) {
            toast("Set Backend URL first");
            return;
        }
        setBusy(true);
        new Thread(() -> {
            try {
                URL url = new URL(base + path);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod(method);
                conn.setConnectTimeout(8000);
                conn.setReadTimeout(240000);
                conn.setRequestProperty("Accept", "application/json");
                String token = tokenInput == null ? prefs.getString(KEY_TOKEN, "") : tokenInput.getText().toString().trim();
                if (!token.isEmpty()) {
                    conn.setRequestProperty("Authorization", "Bearer " + token);
                }
                if (body != null) {
                    byte[] data = body.getBytes(StandardCharsets.UTF_8);
                    conn.setDoOutput(true);
                    conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                    conn.setRequestProperty("Content-Length", String.valueOf(data.length));
                    OutputStream out = conn.getOutputStream();
                    out.write(data);
                    out.close();
                }
                int code = conn.getResponseCode();
                InputStream stream = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
                String response = readAll(stream);
                if (code >= 200 && code < 300) {
                    JSONObject json = response.trim().isEmpty() ? new JSONObject() : new JSONObject(response);
                    runOnUiThread(() -> {
                        setBusy(false);
                        callback.ok(json);
                    });
                } else {
                    runOnUiThread(() -> {
                        setBusy(false);
                        callback.fail("HTTP " + code + ": " + response);
                    });
                }
            } catch (Exception e) {
                runOnUiThread(() -> {
                    setBusy(false);
                    callback.fail(e.getMessage() == null ? "Request failed" : e.getMessage());
                });
            }
        }).start();
    }

    private JSONArray supabaseArray(String method, String path, String body) throws Exception {
        String raw = supabaseRaw(method, path, body, false);
        return raw.trim().isEmpty() ? new JSONArray() : new JSONArray(raw);
    }

    private String supabaseRaw(String method, String path, String body, boolean write) throws Exception {
        String base = cleanSupabaseUrl();
        String key = cleanSupabaseAnonKey();
        if (base.isEmpty() || key.isEmpty()) {
            throw new IllegalStateException("Set Supabase URL and anon key first");
        }
        URL url = new URL(base + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod(method);
        conn.setConnectTimeout(8000);
        conn.setReadTimeout(60000);
        conn.setRequestProperty("Accept", "application/json");
        conn.setRequestProperty("apikey", key);
        conn.setRequestProperty("Authorization", "Bearer " + key);
        if (write) {
            conn.setRequestProperty("Prefer", "return=minimal");
        }
        if (body != null) {
            byte[] data = body.getBytes(StandardCharsets.UTF_8);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("Content-Length", String.valueOf(data.length));
            OutputStream out = conn.getOutputStream();
            out.write(data);
            out.close();
        }
        int code = conn.getResponseCode();
        InputStream stream = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
        String response = readAll(stream);
        if (code < 200 || code >= 300) {
            throw new IllegalStateException("Supabase HTTP " + code + ": " + response);
        }
        return response;
    }

    private String readAll(InputStream stream) throws Exception {
        if (stream == null) return "";
        BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8));
        StringBuilder builder = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            builder.append(line);
        }
        return builder.toString();
    }

    private void setBusy(boolean busy) {
        if (progress != null) {
            progress.setVisibility(busy ? View.VISIBLE : View.GONE);
        }
    }

    private String cleanBaseUrl() {
        String value = urlInput == null ? prefs.getString(KEY_BASE_URL, "") : urlInput.getText().toString().trim();
        while (value.endsWith("/")) value = value.substring(0, value.length() - 1);
        return value;
    }

    private boolean hasSupabase() {
        return !cleanSupabaseUrl().isEmpty() && !cleanSupabaseAnonKey().isEmpty();
    }

    private String cleanSupabaseUrl() {
        String value = supabaseUrlInput == null ? prefs.getString(KEY_SUPABASE_URL, "") : supabaseUrlInput.getText().toString().trim();
        while (value.endsWith("/")) value = value.substring(0, value.length() - 1);
        return value;
    }

    private String cleanSupabaseAnonKey() {
        return supabaseKeyInput == null ? prefs.getString(KEY_SUPABASE_ANON_KEY, "") : supabaseKeyInput.getText().toString().trim();
    }

    private LinearLayout panel() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(14), dp(14), dp(14), dp(14));
        box.setBackgroundColor(card);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, dp(8), 0, dp(10));
        box.setLayoutParams(params);
        return box;
    }

    private EditText input(String hint) {
        EditText input = new EditText(this);
        input.setHint(hint);
        input.setSingleLine(true);
        input.setTextSize(15);
        input.setTextColor(ink);
        input.setHintTextColor(0xFF8A8D91);
        input.setPadding(dp(10), dp(8), dp(10), dp(8));
        return input;
    }

    private Button button(String text, int color) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextColor(0xFFFFFFFF);
        button.setTextSize(14);
        button.setBackgroundColor(color);
        return button;
    }

    private TextView body(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(15);
        view.setLineSpacing(dp(2), 1.0f);
        view.setTextColor(ink);
        return view;
    }

    private TextView smallLabel(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(12);
        view.setTypeface(Typeface.DEFAULT_BOLD);
        view.setTextColor(muted);
        view.setPadding(0, 0, 0, dp(4));
        return view;
    }

    private void addSectionTitle(String text) {
        TextView title = new TextView(this);
        title.setText(text);
        title.setTextColor(ink);
        title.setTextSize(18);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, dp(20), 0, dp(6));
        root.addView(title);
    }

    private LinearLayout.LayoutParams weightParams() {
        return new LinearLayout.LayoutParams(0, -2, 1f);
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    private interface ApiCallback {
        void ok(JSONObject json);
        void fail(String message);
    }
}
