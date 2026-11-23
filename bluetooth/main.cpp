/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 *
 * hy300-bt-uart: prepara a UART do Bluetooth do AIC8800 para o HAL AIDL padrão do AOSP. Roda no
 * boot, antes do HAL. No modo "uart" ajusta e sai; no modo "hci" segura o tty com a disciplina
 * de linha do kernel até ser parado.
 */

#define LOG_TAG "hy300-bt-uart"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android-base/unique_fd.h>
#include <fcntl.h>
#include <unistd.h>

#include "BtUart.h"

using namespace hy300::bluetooth;

int main() {
    const BtUartConfig config = buildBtUartConfig(
            [](const char* name) { return android::base::GetProperty(name, ""); });
    LOG_IF(WARNING, !powerOnBluetoothRfkill()) << "sem rfkill de Bluetooth";

    android::base::unique_fd fd(open(config.tty.c_str(), O_RDWR | O_NOCTTY | O_CLOEXEC));
    if (fd < 0) {
        PLOG(ERROR) << "não abriu " << config.tty;
        return 1;
    }
    if (!configureTty(fd.get(), config)) {
        PLOG(ERROR) << "não ajustou " << config.tty << " em " << config.baud;
        return 1;
    }
    if (config.mode == BtMode::kRawUart) {
        LOG(INFO) << config.tty << " em " << config.baud << " para o HAL";
        return 0;
    }
    if (!attachHciLineDiscipline(fd.get())) {
        PLOG(ERROR) << "disciplina de linha N_HCI recusada (falta CONFIG_BT_HCIUART_H4?)";
        return 1;
    }
    LOG(INFO) << config.tty << " ligado ao hci do kernel";
    for (;;) {
        pause();
    }
}
