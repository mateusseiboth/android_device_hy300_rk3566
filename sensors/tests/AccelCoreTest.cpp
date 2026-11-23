/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 *
 * Testes do núcleo do HAL de sensores do HY300, no host, com dispositivos falsos: uma árvore
 * sysfs de IIO e de input num diretório temporário e um pipe no lugar do /dev/input/eventN.
 */

#include <gtest/gtest.h>
#include <linux/input.h>
#include <unistd.h>

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>

#include "AccelConfig.h"
#include "AccelReader.h"
#include "IioAccelSource.h"
#include "InputAccelSource.h"
#include "OpenAccelSource.h"

namespace hy300::sensors {
namespace {

namespace fs = std::filesystem;

class TempDir {
  public:
    TempDir() {
        std::string pattern = (fs::temp_directory_path() / "hy300-sensors-XXXXXX").string();
        path_ = mkdtemp(pattern.data());
    }
    ~TempDir() { fs::remove_all(path_); }
    const fs::path& path() const { return path_; }

    void writeFile(const fs::path& relative, const std::string& content) const {
        fs::create_directories((path_ / relative).parent_path());
        std::ofstream(path_ / relative) << content;
    }

  private:
    fs::path path_;
};

constexpr float kTolerance = 1e-4f;

// ---- configuração ----

TEST(AccelAxisMapTest, identityKeepsTheAxes) {
    const auto map = parseAxisMap("x,y,z");
    ASSERT_TRUE(map.has_value());
    const Vec3 out = applyAxisMap(*map, {1.f, 2.f, 3.f});
    EXPECT_FLOAT_EQ(out.x, 1.f);
    EXPECT_FLOAT_EQ(out.y, 2.f);
    EXPECT_FLOAT_EQ(out.z, 3.f);
}

TEST(AccelAxisMapTest, swapsAndInvertsAxes) {
    const auto map = parseAxisMap("-y, x ,-z");
    ASSERT_TRUE(map.has_value());
    const Vec3 out = applyAxisMap(*map, {1.f, 2.f, 3.f});
    EXPECT_FLOAT_EQ(out.x, -2.f);
    EXPECT_FLOAT_EQ(out.y, 1.f);
    EXPECT_FLOAT_EQ(out.z, -3.f);
}

TEST(AccelAxisMapTest, rejectsRepeatedOrUnknownAxes) {
    EXPECT_FALSE(parseAxisMap("x,x,z").has_value());
    EXPECT_FALSE(parseAxisMap("x,y").has_value());
    EXPECT_FALSE(parseAxisMap("x,y,w").has_value());
    EXPECT_FALSE(parseAxisMap("").has_value());
}

TEST(AccelConfigTest, defaultsAreTheRockchipGsensor) {
    const AccelConfig config = buildAccelConfig([](const char*) { return std::string(); });
    EXPECT_EQ(config.backend, Backend::kRockchipGsensor);
    EXPECT_EQ(config.device, "gsensor");
    EXPECT_EQ(config.control, "/dev/mma8452_daemon");
    EXPECT_NEAR(config.scale, 9.80665f / 16384.f, 1e-9f);
}

TEST(AccelConfigTest, readsEachProperty) {
    const AccelConfig config = buildAccelConfig([](const char* name) -> std::string {
        const std::string key = name;
        if (key == "ro.vendor.hy300.accel.backend") return "iio";
        if (key == "ro.vendor.hy300.accel.device") return "lis3dh";
        if (key == "ro.vendor.hy300.accel.axes") return "-x,y,-z";
        if (key == "ro.vendor.hy300.accel.scale") return "0.5";
        return "";
    });
    EXPECT_EQ(config.backend, Backend::kIio);
    EXPECT_EQ(config.device, "lis3dh");
    EXPECT_FLOAT_EQ(config.scale, 0.5f);
    EXPECT_FLOAT_EQ(applyAxisMap(config.axes, {1.f, 1.f, 1.f}).x, -1.f);
}

TEST(AccelConfigTest, invalidValuesFallBackToDefaults) {
    const AccelConfig config = buildAccelConfig([](const char* name) -> std::string {
        const std::string key = name;
        if (key == "ro.vendor.hy300.accel.backend") return "bluetooth";
        if (key == "ro.vendor.hy300.accel.axes") return "q,r,s";
        if (key == "ro.vendor.hy300.accel.scale") return "-1";
        return "";
    });
    EXPECT_EQ(config.backend, Backend::kRockchipGsensor);
    EXPECT_FLOAT_EQ(applyAxisMap(config.axes, {1.f, 2.f, 3.f}).y, 2.f);
    EXPECT_NEAR(config.scale, 9.80665f / 16384.f, 1e-9f);
}

// ---- IIO ----

TEST(IioAccelSourceTest, findsTheDeviceByName) {
    TempDir sys;
    sys.writeFile("iio:device0/name", "rk-saradc\n");
    sys.writeFile("iio:device1/name", "lis3dh\n");
    EXPECT_EQ(findIioDevice(sys.path(), "lis3dh"), sys.path() / "iio:device1");
    EXPECT_FALSE(findIioDevice(sys.path(), "bmi160").has_value());
}

TEST(IioAccelSourceTest, readsRawTimesScalePlusOffset) {
    TempDir sys;
    sys.writeFile("in_accel_x_raw", "100\n");
    sys.writeFile("in_accel_y_raw", "-50\n");
    sys.writeFile("in_accel_z_raw", "1000\n");
    sys.writeFile("in_accel_scale", "0.009580\n");
    IioAccelSource source(sys.path());
    const auto sample = source.read();
    ASSERT_TRUE(sample.has_value());
    EXPECT_NEAR(sample->x, 0.958f, kTolerance);
    EXPECT_NEAR(sample->y, -0.479f, kTolerance);
    EXPECT_NEAR(sample->z, 9.58f, kTolerance);
    EXPECT_TRUE(source.isScaled());
}

TEST(IioAccelSourceTest, perAxisScaleWins) {
    TempDir sys;
    sys.writeFile("in_accel_x_raw", "10\n");
    sys.writeFile("in_accel_y_raw", "10\n");
    sys.writeFile("in_accel_z_raw", "10\n");
    sys.writeFile("in_accel_scale", "1\n");
    sys.writeFile("in_accel_z_scale", "2\n");
    IioAccelSource source(sys.path());
    const auto sample = source.read();
    ASSERT_TRUE(sample.has_value());
    EXPECT_FLOAT_EQ(sample->x, 10.f);
    EXPECT_FLOAT_EQ(sample->z, 20.f);
}

TEST(IioAccelSourceTest, missingAxisGivesNoSample) {
    TempDir sys;
    sys.writeFile("in_accel_x_raw", "10\n");
    IioAccelSource source(sys.path());
    EXPECT_FALSE(source.read().has_value());
}

// ---- input ----

TEST(InputAccelSourceTest, findsTheEventNodeByName) {
    TempDir sys;
    sys.writeFile("event0/device/name", "fdd70030.pwm\n");
    sys.writeFile("event3/device/name", "gsensor\n");
    EXPECT_EQ(findInputEvent(sys.path(), "gsensor"), "event3");
    EXPECT_FALSE(findInputEvent(sys.path(), "compass").has_value());
}

void writeEvent(int fd, uint16_t type, uint16_t code, int32_t value) {
    input_event event{};
    event.type = type;
    event.code = code;
    event.value = value;
    ASSERT_EQ(write(fd, &event, sizeof(event)), static_cast<ssize_t>(sizeof(event)));
}

class InputAccelSourceStreamTest : public ::testing::Test {
  protected:
    void SetUp() override { ASSERT_EQ(pipe(fds_), 0); }
    void TearDown() override { close(fds_[1]); }
    int fds_[2] = {-1, -1};
};

TEST_F(InputAccelSourceStreamTest, sampleOnlyAfterSynReport) {
    InputAccelSource source(fds_[0]);
    writeEvent(fds_[1], EV_ABS, ABS_X, 16384);
    writeEvent(fds_[1], EV_ABS, ABS_Y, -8192);
    EXPECT_FALSE(source.read().has_value());

    writeEvent(fds_[1], EV_ABS, ABS_Z, 4);
    writeEvent(fds_[1], EV_SYN, SYN_REPORT, 0);
    const auto sample = source.read();
    ASSERT_TRUE(sample.has_value());
    EXPECT_FLOAT_EQ(sample->x, 16384.f);
    EXPECT_FLOAT_EQ(sample->y, -8192.f);
    EXPECT_FLOAT_EQ(sample->z, 4.f);
    EXPECT_FALSE(source.isScaled());
}

TEST_F(InputAccelSourceStreamTest, keepsUnchangedAxesAndTheLastSample) {
    InputAccelSource source(fds_[0]);
    writeEvent(fds_[1], EV_ABS, ABS_X, 1);
    writeEvent(fds_[1], EV_ABS, ABS_Y, 2);
    writeEvent(fds_[1], EV_ABS, ABS_Z, 3);
    writeEvent(fds_[1], EV_SYN, SYN_REPORT, 0);
    writeEvent(fds_[1], EV_ABS, ABS_Y, 20);
    writeEvent(fds_[1], EV_SYN, SYN_REPORT, 0);
    auto sample = source.read();
    ASSERT_TRUE(sample.has_value());
    EXPECT_FLOAT_EQ(sample->x, 1.f);
    EXPECT_FLOAT_EQ(sample->y, 20.f);

    // Nada novo no pipe: devolve a última amostra, sem bloquear.
    sample = source.read();
    ASSERT_TRUE(sample.has_value());
    EXPECT_FLOAT_EQ(sample->y, 20.f);
}

TEST_F(InputAccelSourceStreamTest, synDroppedDiscardsThePartialSample) {
    InputAccelSource source(fds_[0]);
    writeEvent(fds_[1], EV_ABS, ABS_X, 5);
    writeEvent(fds_[1], EV_SYN, SYN_DROPPED, 0);
    writeEvent(fds_[1], EV_SYN, SYN_REPORT, 0);
    writeEvent(fds_[1], EV_ABS, ABS_X, 7);
    writeEvent(fds_[1], EV_SYN, SYN_REPORT, 0);
    const auto sample = source.read();
    ASSERT_TRUE(sample.has_value());
    EXPECT_FLOAT_EQ(sample->x, 7.f);
}

// ---- leitura em m/s² ----

class FakeSource : public AccelSource {
  public:
    explicit FakeSource(bool scaled) : scaled_(scaled) {}
    std::optional<Vec3> read() override { return next; }
    bool isScaled() const override { return scaled_; }
    std::optional<Vec3> next;

  private:
    bool scaled_;
};

TEST(AccelReaderTest, rawSourceUsesTheConfiguredScaleAndAxes) {
    auto source = std::make_unique<FakeSource>(false);
    source->next = Vec3{16384.f, 0.f, -16384.f};
    AccelConfig config;
    config.scale = 9.80665f / 16384.f;
    config.axes = *parseAxisMap("z,y,x");
    AccelReader reader(std::move(source), config);
    const auto sample = reader.read();
    ASSERT_TRUE(sample.has_value());
    EXPECT_NEAR(sample->x, -9.80665f, kTolerance);
    EXPECT_NEAR(sample->z, 9.80665f, kTolerance);
}

TEST(AccelReaderTest, scaledSourceIgnoresTheConfiguredScale) {
    auto source = std::make_unique<FakeSource>(true);
    source->next = Vec3{0.f, 9.8f, 0.f};
    AccelConfig config;
    config.scale = 1000.f;
    AccelReader reader(std::move(source), config);
    const auto sample = reader.read();
    ASSERT_TRUE(sample.has_value());
    EXPECT_FLOAT_EQ(sample->y, 9.8f);
}

TEST(AccelReaderTest, noSampleStaysEmpty) {
    AccelReader reader(std::make_unique<FakeSource>(false), AccelConfig{});
    EXPECT_FALSE(reader.read().has_value());
}

}  // namespace
}  // namespace hy300::sensors

namespace hy300::sensors {
namespace {

// ---- escolha da fonte pela configuração ----

TEST(OpenAccelSourceTest, iioBackendFindsTheDeviceByName) {
    TempDir sys;
    sys.writeFile("iio/iio:device2/name", "lis3dh\n");
    sys.writeFile("iio/iio:device2/in_accel_x_raw", "1\n");
    sys.writeFile("iio/iio:device2/in_accel_y_raw", "2\n");
    sys.writeFile("iio/iio:device2/in_accel_z_raw", "3\n");
    AccelConfig config;
    config.backend = Backend::kIio;
    config.device = "lis3dh";
    const SysfsRoots roots{sys.path() / "iio", sys.path() / "input", sys.path() / "dev"};
    auto source = openAccelSource(config, roots);
    ASSERT_NE(source, nullptr);
    EXPECT_FLOAT_EQ(source->read()->z, 3.f);
}

TEST(OpenAccelSourceTest, inputBackendOpensTheEventNodeOfTheName) {
    TempDir sys;
    sys.writeFile("input/event5/device/name", "gsensor\n");
    sys.writeFile("dev/event5", "");
    AccelConfig config;
    config.backend = Backend::kInput;
    const SysfsRoots roots{sys.path() / "iio", sys.path() / "input", sys.path() / "dev"};
    auto source = openAccelSource(config, roots);
    ASSERT_NE(source, nullptr);
    EXPECT_FALSE(source->isScaled());
}

TEST(OpenAccelSourceTest, missingDeviceGivesNoSource) {
    TempDir sys;
    AccelConfig config;
    const SysfsRoots roots{sys.path() / "iio", sys.path() / "input", sys.path() / "dev"};
    EXPECT_EQ(openAccelSource(config, roots), nullptr);
    config.backend = Backend::kIio;
    EXPECT_EQ(openAccelSource(config, roots), nullptr);
}

}  // namespace
}  // namespace hy300::sensors
