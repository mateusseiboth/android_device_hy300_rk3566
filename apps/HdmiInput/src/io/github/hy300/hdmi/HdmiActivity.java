package io.github.hy300.hdmi;

import android.app.Activity;
import android.content.Intent;
import android.media.tv.TvContract;
import android.media.tv.TvInputInfo;
import android.media.tv.TvInputManager;
import android.media.tv.TvView;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.TextView;

/**
 * Tela cheia da entrada HDMI: um TvView sintonizado no "passthrough" do nosso TV input. Abre pelo
 * launcher, pelo app de configurações ("Abrir HDMI") e pelo seletor de entradas do Android TV
 * (ACTION_VIEW com o URI de passthrough).
 */
public final class HdmiActivity extends Activity {
    private TvView tvView;
    private TextView message;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.hdmi);
        tvView = findViewById(R.id.tv_view);
        message = findViewById(R.id.message);
        tvView.setCallback(new TvView.TvInputCallback() {
            @Override
            public void onVideoAvailable(String inputId) {
                message.setVisibility(View.GONE);
            }

            @Override
            public void onVideoUnavailable(String inputId, int reason) {
                message.setText(R.string.hdmi_no_signal);
                message.setVisibility(View.VISIBLE);
            }
        });
    }

    @Override
    protected void onStart() {
        super.onStart();
        String inputId = inputIdFrom(getIntent());
        if (inputId == null) {
            message.setText(R.string.hdmi_missing);
            message.setVisibility(View.VISIBLE);
            return;
        }
        tvView.tune(inputId, TvContract.buildChannelUriForPassthroughInput(inputId));
    }

    @Override
    protected void onStop() {
        tvView.reset();
        super.onStop();
    }

    private String inputIdFrom(Intent intent) {
        Uri data = intent.getData();
        if (data != null && TvContract.isChannelUriForPassthroughInput(data)) {
            return data.getPathSegments().get(1);
        }
        TvInputManager manager = getSystemService(TvInputManager.class);
        for (TvInputInfo info : manager.getTvInputList()) {
            boolean ours = getPackageName().equals(info.getServiceInfo().packageName);
            if (ours && info.getType() == TvInputInfo.TYPE_HDMI) return info.getId();
        }
        return null;
    }
}
