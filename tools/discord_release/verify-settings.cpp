// Exercise the actual compiled settings widget and configuration persistence.
#include <iostream>
#include <QApplication>
#include <QCheckBox>
#include "citra_qt/configuration/config.h"
#include "citra_qt/configuration/configure_network.h"
#include "citra_qt/uisettings.h"
#include "common/file_util.h"
#include "common/settings.h"

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    if (argc != 3) return 2;
    FileUtil::SetUserPath(std::string(argv[1]) + "/");
    Settings::SetConfiguringGlobal(true);
    const std::string mode = argv[2];
    const bool expected = mode.ends_with("on");
    QtConfig config;
    ConfigureWeb page;
    auto* toggle = page.findChild<QCheckBox*>(QStringLiteral("toggle_discordrpc"));
    if (!toggle || !toggle->isEnabled()) {
        std::cerr << "Discord checkbox is missing or disabled\n";
        return 3;
    }
    if (mode.starts_with("write")) {
        if (toggle->isChecked() != expected) toggle->click();
        page.ApplyConfiguration();
        config.Save();
    }
    if (toggle->isChecked() != expected ||
        UISettings::values.enable_discord_presence.GetValue() != expected) {
        std::cerr << "Saved setting and checkbox do not match\n";
        return 4;
    }
    std::cout << mode << ": checkbox enabled, value=" << expected << ", passed\n";
}
