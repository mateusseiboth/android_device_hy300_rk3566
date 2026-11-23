package io.github.hy300.hdmi;

import android.os.IBinder;
import android.os.RemoteException;
import android.os.ServiceManager;
import android.util.Log;
import android.view.Surface;

import vendor.hy300.hdmiin.HdmiSignal;
import vendor.hy300.hdmiin.IHdmiCapture;

/** Cliente do serviço de captura do vendor (vendor.hy300.hdmiin.IHdmiCapture/default). */
final class CaptureClient {
    private static final String TAG = "HY300Hdmi";
    private static final String INSTANCE = IHdmiCapture.DESCRIPTOR + "/default";

    private IHdmiCapture service;

    private synchronized IHdmiCapture service() {
        if (service == null || !service.asBinder().isBinderAlive()) {
            IBinder binder = ServiceManager.waitForDeclaredService(INSTANCE);
            service = binder == null ? null : IHdmiCapture.Stub.asInterface(binder);
        }
        return service;
    }

    Signal signal() {
        try {
            IHdmiCapture s = service();
            if (s == null) return Signal.NO_CABLE;
            HdmiSignal signal = s.getSignal();
            return Signal.of(signal.cablePresent, signal.width, signal.height);
        } catch (RemoteException e) {
            Log.w(TAG, "getSignal falhou", e);
            return Signal.NO_CABLE;
        }
    }

    boolean start(Surface surface) {
        try {
            IHdmiCapture s = service();
            if (s == null) return false;
            s.startPreview(surface);
            return true;
        } catch (RemoteException | RuntimeException e) {
            Log.w(TAG, "startPreview falhou", e);
            return false;
        }
    }

    void stop() {
        try {
            IHdmiCapture s = service();
            if (s != null) s.stopPreview();
        } catch (RemoteException e) {
            Log.w(TAG, "stopPreview falhou", e);
        }
    }
}
