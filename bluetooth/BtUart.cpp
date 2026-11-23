/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "BtUart.h"

#include <sys/ioctl.h>

#include <charconv>
#include <fstream>
#include <map>
#include <system_error>

namespace hy300::bluetooth {
namespace {

namespace fs = std::filesystem;

// include/uapi/linux/tty.h e drivers/bluetooth/hci_uart.h do kernel.
constexpr int kLineDisciplineHci = 15;  // N_HCI
constexpr unsigned long kHciUartSetProto = _IOW('U', 200, int);
constexpr int kHciUartH4 = 0;

std::optional<std::string> readLine(const fs::path& path) {
    std::ifstream file(path);
    std::string line;
    if (!file || !std::getline(file, line)) {
        return std::nullopt;
    }
    return line;
}

std::optional<int> parseInt(const std::string& text) {
    int value = 0;
    const char* end = text.data() + text.size();
    const auto [ptr, error] = std::from_chars(text.data(), end, value);
    if (text.empty() || error != std::errc() || ptr != end) {
        return std::nullopt;
    }
    return value;
}

}  // namespace

std::optional<speed_t> toSpeed(int baud) {
    static const std::map<int, speed_t> kSpeeds = {
            {115200, B115200},   {230400, B230400},   {460800, B460800},
            {921600, B921600},   {1000000, B1000000}, {1500000, B1500000},
            {2000000, B2000000}, {3000000, B3000000}, {4000000, B4000000},
    };
    const auto it = kSpeeds.find(baud);
    return it == kSpeeds.end() ? std::nullopt : std::optional<speed_t>(it->second);
}

BtUartConfig buildBtUartConfig(const PropertyGetter& get) {
    BtUartConfig config;
    if (const std::string tty = get("ro.vendor.hy300.bt.tty"); !tty.empty()) {
        config.tty = tty;
    }
    if (const auto baud = parseInt(get("ro.vendor.hy300.bt.baud")); baud && toSpeed(*baud)) {
        config.baud = *baud;
    }
    if (const std::string flow = get("ro.vendor.hy300.bt.flow"); flow == "0" || flow == "1") {
        config.flowControl = flow == "1";
    }
    static const std::map<std::string, BtMode> kModes = {{"uart", BtMode::kRawUart},
                                                         {"hci", BtMode::kKernelHci}};
    if (const auto it = kModes.find(get("ro.vendor.hy300.bt.mode")); it != kModes.end()) {
        config.mode = it->second;
    }
    return config;
}

bool powerOnBluetoothRfkill(const fs::path& root) {
    std::error_code error;
    for (const auto& entry : fs::directory_iterator(root, error)) {
        if (readLine(entry.path() / "type") == "bluetooth") {
            std::ofstream state(entry.path() / "state");
            state << "1";
            return static_cast<bool>(state);
        }
    }
    return false;
}

bool configureTty(int fd, const BtUartConfig& config) {
    const auto speed = toSpeed(config.baud);
    termios settings{};
    if (!speed || tcgetattr(fd, &settings) != 0) {
        return false;
    }
    cfmakeraw(&settings);
    settings.c_cflag |= CLOCAL | CREAD;
    settings.c_cflag = config.flowControl ? (settings.c_cflag | CRTSCTS)
                                          : (settings.c_cflag & ~static_cast<tcflag_t>(CRTSCTS));
    cfsetospeed(&settings, *speed);
    cfsetispeed(&settings, *speed);
    return tcsetattr(fd, TCSANOW, &settings) == 0 && tcflush(fd, TCIOFLUSH) == 0;
}

bool attachHciLineDiscipline(int fd) {
    int discipline = kLineDisciplineHci;
    int protocol = kHciUartH4;
    return ioctl(fd, TIOCSETD, &discipline) == 0 && ioctl(fd, kHciUartSetProto, protocol) == 0;
}

}  // namespace hy300::bluetooth
