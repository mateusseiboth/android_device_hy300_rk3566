/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 *
 * Testes do hy300-bt-uart no host: rfkill numa árvore sysfs falsa e termios num pty.
 */

#include <gtest/gtest.h>
#include <pty.h>
#include <termios.h>
#include <unistd.h>

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

#include "BtUart.h"

namespace hy300::bluetooth {
namespace {

namespace fs = std::filesystem;

class TempDir {
  public:
    TempDir() {
        std::string pattern = (fs::temp_directory_path() / "hy300-bt-XXXXXX").string();
        path_ = mkdtemp(pattern.data());
    }
    ~TempDir() { fs::remove_all(path_); }
    const fs::path& path() const { return path_; }
    void writeFile(const fs::path& relative, const std::string& content) const {
        fs::create_directories((path_ / relative).parent_path());
        std::ofstream(path_ / relative) << content;
    }
    std::string readFile(const fs::path& relative) const {
        std::ifstream file(path_ / relative);
        std::string line;
        std::getline(file, line);
        return line;
    }

  private:
    fs::path path_;
};

TEST(BtUartConfigTest, defaultsAreTheAic8800OnUart1) {
    const BtUartConfig config = buildBtUartConfig([](const char*) { return std::string(); });
    EXPECT_EQ(config.tty, "/dev/ttyS1");
    EXPECT_EQ(config.baud, 1500000);
    EXPECT_TRUE(config.flowControl);
    EXPECT_EQ(config.mode, BtMode::kRawUart);
}

TEST(BtUartConfigTest, readsTheProperties) {
    const BtUartConfig config = buildBtUartConfig([](const char* name) -> std::string {
        const std::string key = name;
        if (key == "ro.vendor.hy300.bt.tty") return "/dev/ttyS3";
        if (key == "ro.vendor.hy300.bt.baud") return "115200";
        if (key == "ro.vendor.hy300.bt.flow") return "0";
        if (key == "ro.vendor.hy300.bt.mode") return "hci";
        return "";
    });
    EXPECT_EQ(config.tty, "/dev/ttyS3");
    EXPECT_EQ(config.baud, 115200);
    EXPECT_FALSE(config.flowControl);
    EXPECT_EQ(config.mode, BtMode::kKernelHci);
}

TEST(BtUartConfigTest, unsupportedBaudFallsBackToTheDefault) {
    const BtUartConfig config = buildBtUartConfig([](const char* name) -> std::string {
        return std::string(name) == "ro.vendor.hy300.bt.baud" ? "1234" : "";
    });
    EXPECT_EQ(config.baud, 1500000);
}

TEST(BtUartSpeedTest, mapsTheUsualRates) {
    EXPECT_EQ(toSpeed(115200), std::optional<speed_t>(B115200));
    EXPECT_EQ(toSpeed(1500000), std::optional<speed_t>(B1500000));
    EXPECT_EQ(toSpeed(3000000), std::optional<speed_t>(B3000000));
    EXPECT_FALSE(toSpeed(1234).has_value());
}

TEST(BtRfkillTest, powersOnOnlyTheBluetoothSwitch) {
    TempDir sys;
    sys.writeFile("rfkill0/type", "wlan\n");
    sys.writeFile("rfkill0/state", "0\n");
    sys.writeFile("rfkill1/type", "bluetooth\n");
    sys.writeFile("rfkill1/state", "0\n");
    EXPECT_TRUE(powerOnBluetoothRfkill(sys.path()));
    EXPECT_EQ(sys.readFile("rfkill1/state"), "1");
    EXPECT_EQ(sys.readFile("rfkill0/state"), "0");
}

TEST(BtRfkillTest, withoutSwitchReportsFalse) {
    TempDir sys;
    sys.writeFile("rfkill0/type", "wlan\n");
    EXPECT_FALSE(powerOnBluetoothRfkill(sys.path()));
}

TEST(BtTtyTest, setsRawSpeedAndFlowControl) {
    int master = -1;
    int slave = -1;
    ASSERT_EQ(openpty(&master, &slave, nullptr, nullptr, nullptr), 0);
    BtUartConfig config;
    ASSERT_TRUE(configureTty(slave, config));

    termios settings{};
    ASSERT_EQ(tcgetattr(slave, &settings), 0);
    EXPECT_EQ(cfgetospeed(&settings), static_cast<speed_t>(B1500000));
    EXPECT_EQ(cfgetispeed(&settings), static_cast<speed_t>(B1500000));
    EXPECT_NE(settings.c_cflag & CRTSCTS, 0U);
    EXPECT_EQ(settings.c_lflag & ICANON, 0U);
    EXPECT_EQ(settings.c_cflag & CSIZE, static_cast<tcflag_t>(CS8));
    close(slave);
    close(master);
}

}  // namespace
}  // namespace hy300::bluetooth
