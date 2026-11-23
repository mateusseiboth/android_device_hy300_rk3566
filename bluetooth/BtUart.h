/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <termios.h>

#include <filesystem>
#include <functional>
#include <optional>
#include <string>

namespace hy300::bluetooth {

// Como o Bluetooth do AIC8800 chega ao HAL AIDL padrão do AOSP
// (android.hardware.bluetooth-service.default):
//  - kRawUart: o HAL abre o tty (vendor.ser.bt-uart) e fala H4 direto; aqui só a velocidade e o
//    controle de fluxo, que o HAL não ajusta (cfmakeraw mantém os dois);
//  - kKernelHci: a disciplina de linha N_HCI (H4) do kernel vira hci0 e o HAL abre o canal de
//    usuário do hci0. Exige CONFIG_BT_HCIUART_H4; este processo segura o tty enquanto viver.
enum class BtMode { kRawUart, kKernelHci };

struct BtUartConfig {
    std::string tty = "/dev/ttyS1";
    int baud = 1500000;  // o patch do aic8800_bsp deixa a UART do chip em 1,5 Mbaud
    bool flowControl = true;
    BtMode mode = BtMode::kRawUart;
};

using PropertyGetter = std::function<std::string(const char* name)>;

// ro.vendor.hy300.bt.{tty,baud,flow,mode}; valor vazio ou inválido fica no padrão.
BtUartConfig buildBtUartConfig(const PropertyGetter& get);

std::optional<speed_t> toSpeed(int baud);

// Liga o rfkill de tipo "bluetooth" (o aic8800_bsp registra um). false se não houver.
bool powerOnBluetoothRfkill(const std::filesystem::path& root = "/sys/class/rfkill");

// 8N1 cru, na velocidade configurada, com ou sem RTS/CTS.
bool configureTty(int fd, const BtUartConfig& config);

// Disciplina de linha N_HCI com o protocolo H4: o kernel cria o hci0.
bool attachHciLineDiscipline(int fd);

}  // namespace hy300::bluetooth
