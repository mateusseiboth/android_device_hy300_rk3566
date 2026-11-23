package io.github.hy300.hdmi;

import android.content.ComponentName;
import android.content.Context;
import android.media.tv.TvInputHardwareInfo;
import android.media.tv.TvInputInfo;
import android.media.tv.TvInputManager;
import android.media.tv.TvInputService;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Surface;

import java.util.HashMap;
import java.util.Map;

/**
 * TV input da entrada HDMI. O HAL de TV input (tvinput/) informa o dispositivo HDMI e o framework
 * chama onHardwareAdded; a sessão não usa o sideband do HAL: entrega a Surface do TvView ao
 * serviço de captura do vendor, que escreve nela pela RGA. A imagem é uma camada comum (keystone
 * e BCSH valem), e o áudio vai ao alto-falante por um patch de áudio.
 */
public final class HdmiInputService extends TvInputService {
    private static final String TAG = "HY300Hdmi";
    private final Map<Integer, String> inputs = new HashMap<>();

    @Override
    public TvInputInfo onHardwareAdded(TvInputHardwareInfo hardware) {
        if (hardware.getType() != TvInputHardwareInfo.TV_INPUT_TYPE_HDMI) return null;
        try {
            TvInputInfo info = new TvInputInfo.Builder(this,
                    new ComponentName(this, HdmiInputService.class))
                    .setTvInputHardwareInfo(hardware)
                    .setLabel(getString(R.string.hdmi_label))
                    .build();
            inputs.put(hardware.getDeviceId(), info.getId());
            return info;
        } catch (Exception e) {
            Log.e(TAG, "TvInputInfo do HDMI falhou", e);
            return null;
        }
    }

    @Override
    public String onHardwareRemoved(TvInputHardwareInfo hardware) {
        return inputs.remove(hardware.getDeviceId());
    }

    @Override
    public Session onCreateSession(String inputId) {
        return new HdmiSession(this);
    }

    private static final class HdmiSession extends Session {
        private static final long SIGNAL_POLL_MS = 1000;

        private final CaptureClient capture = new CaptureClient();
        private final AudioRoute audio = new AudioRoute();
        private final Handler handler = new Handler(Looper.getMainLooper());
        private Signal reported;

        private final Runnable poll = new Runnable() {
            @Override
            public void run() {
                report(capture.signal());
                handler.postDelayed(this, SIGNAL_POLL_MS);
            }
        };

        HdmiSession(Context context) {
            super(context);
        }

        private void report(Signal signal) {
            if (signal == reported) return;
            reported = signal;
            if (signal == Signal.VIDEO) {
                notifyVideoAvailable();
            } else {
                notifyVideoUnavailable(TvInputManager.VIDEO_UNAVAILABLE_REASON_UNKNOWN);
            }
        }

        @Override
        public boolean onTune(Uri channelUri) {
            audio.start();
            handler.removeCallbacks(poll);
            handler.post(poll);
            return true;
        }

        @Override
        public boolean onSetSurface(Surface surface) {
            if (surface == null) {
                capture.stop();
                return true;
            }
            return capture.start(surface);
        }

        @Override
        public void onSetStreamVolume(float volume) {
        }

        @Override
        public void onSetCaptionEnabled(boolean enabled) {
        }

        @Override
        public void onRelease() {
            handler.removeCallbacks(poll);
            capture.stop();
            audio.stop();
        }
    }
}
