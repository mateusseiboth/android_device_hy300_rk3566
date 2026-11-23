package io.github.hy300.hdmi;

import android.media.AudioDevicePort;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioPatch;
import android.media.AudioPort;
import android.media.AudioPortConfig;
import android.media.AudioSystem;
import android.util.Log;

import java.util.ArrayList;

/**
 * Áudio da entrada HDMI (placa rockchiphdmiin, "HDMI In" CARD_1_DEV_0 no audio policy) no
 * alto-falante enquanto a entrada está aberta: um patch HDMI In -> saída, como o
 * TvInputHardwareManager faz para os TV inputs de hardware. Sem rota direta no audio policy, o
 * AudioFlinger monta a ponte por software. No audio policy o HDMI In é DEVICE_IN_TV_TUNER
 * (embutido): o HAL de áudio de exemplo não aceita o tipo HDMI (conexão "hdmi") anexado.
 */
final class AudioRoute {
    private static final String TAG = "HY300Hdmi";
    static final String HDMI_ADDRESS = "CARD_1_DEV_0";

    private AudioPatch patch;

    synchronized void start() {
        if (patch != null) return;
        ArrayList<AudioDevicePort> ports = new ArrayList<>();
        if (AudioManager.listAudioDevicePorts(ports) != AudioManager.SUCCESS) return;
        int[] roles = new int[ports.size()];
        int[] types = new int[ports.size()];
        String[] addresses = new String[ports.size()];
        for (int i = 0; i < ports.size(); i++) {
            roles[i] = ports.get(i).role();
            types[i] = ports.get(i).type();
            addresses[i] = ports.get(i).address();
        }
        int source = AudioPortChooser.pick(roles, types, addresses, AudioPort.ROLE_SOURCE,
                AudioSystem.DEVICE_IN_TV_TUNER, HDMI_ADDRESS);
        int sink = AudioPortChooser.pick(roles, types, addresses, AudioPort.ROLE_SINK,
                AudioSystem.DEVICE_OUT_SPEAKER, null);
        if (source < 0 || sink < 0) {
            Log.w(TAG, "sem HDMI In ou alto-falante no audio policy");
            return;
        }
        AudioPatch[] created = new AudioPatch[1];
        int result = AudioManager.createAudioPatch(created,
                new AudioPortConfig[]{configOf(ports.get(source), AudioFormat.CHANNEL_IN_DEFAULT)},
                new AudioPortConfig[]{configOf(ports.get(sink), AudioFormat.CHANNEL_OUT_DEFAULT)});
        if (result != AudioManager.SUCCESS) {
            Log.w(TAG, "createAudioPatch falhou: " + result);
            return;
        }
        patch = created[0];
    }

    synchronized void stop() {
        if (patch == null) return;
        AudioManager.releaseAudioPatch(patch);
        patch = null;
    }

    private static AudioPortConfig configOf(AudioDevicePort port, int defaultMask) {
        AudioPortConfig active = port.activeConfig();
        return active != null ? active
                : port.buildConfig(0, defaultMask, AudioFormat.ENCODING_DEFAULT, null);
    }
}
