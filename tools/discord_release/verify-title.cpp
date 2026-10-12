// Exercise the release's real presence formatter and RPC serializer with an isolated loader.
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
#include <discord_rpc.h>
#include "core/core.h"
#include "citra_qt/discord_impl.h"
#include "citra_qt/discord_artwork.h"
#include "serialization.h"

static std::string last_message;

extern "C" void Discord_Initialize(const char*, DiscordEventHandlers*, int, const char*) {}
extern "C" void Discord_Shutdown() {}
extern "C" void Discord_UpdatePresence(const DiscordRichPresence* presence) {
    char buffer[16384];
    const auto size = JsonWriteRichPresenceObj(buffer, sizeof(buffer), 1, 1234, presence);
    last_message.assign(buffer, size);
}
extern "C" void Discord_ClearPresence() {
    Discord_UpdatePresence(nullptr);
}

static void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << '\n';
        std::exit(1);
    }
}

int main() {
    Core::System system;
    DiscordRPC::DiscordImpl presence(system);
    const std::string artwork_base = "https://raw.githubusercontent.com/ghost-land/3dsdb/"
                                     "0c316afaf29c4d01ca88c488b1b6cb6920e9f58e/db/3ds/";
    const auto japanese_icon = artwork_base + "base/0004000000030600/icon.jpg";
    const auto us_icon = artwork_base + "base/0004000000030800/icon.jpg";
    require(DiscordRPC::GetGameArtworkUrl(0x0004000000030600ULL) == japanese_icon,
            "Japanese game artwork does not match its title ID");
    require(DiscordRPC::GetGameArtworkUrl(0x0004000000030800ULL) == us_icon,
            "US game artwork does not match its title ID");
    require(DiscordRPC::GetGameArtworkUrl(0x0004000000040800ULL) ==
                artwork_base + "virtual-console/0004000000040800/icon.jpg",
            "Virtual-console artwork used the wrong category");
    require(DiscordRPC::GetGameArtworkUrl(0).empty(), "Unknown title must not request an image");
    for (const auto& entry : DiscordRPC::GameArtworkCatalog) {
        require(!DiscordRPC::GetGameArtworkUrl(entry.title_id).empty(), "Missing catalogue entry");
    }
    system.loader.program_id = 0x0004000000030600ULL;
    const std::vector<std::pair<std::string, std::string>> cases{
        {"AzaharPlus display test", "AzaharPlus display test"},
        {"Game B", "Game B"},
        {"ゲーム名 \"日本語\"", "ゲーム名 \"日本語\""},
        {std::string(124, 'a') + "あ" + "bbbbbb", std::string(124, 'a') + "..."},
        {std::string(130, 'x'), std::string(125, 'x') + "..."},
        {"", "AzaharPlus"},
    };
    for (const auto& [input, expected] : cases) {
        if (input == "Game B") {
            system.loader.program_id = 0x0004000000030800ULL;
        }
        system.loader.title = input;
        presence.Update(true);
        rapidjson::Document json;
        json.Parse(last_message.c_str());
        require(!json.HasParseError(), "Presence is not valid JSON");
        const auto& activity = json["args"]["activity"];
        require(activity["name"].GetString() == expected, "Wrong card title");
        require(activity["status_display_type"].GetInt() == 0, "Member status must use name");
        require(activity["details"].GetString() == std::string("Nintendo 3DS / AzaharPlus"),
                "Emulator details missing");
        require(activity["timestamps"]["start"].GetInt64() > 0, "Elapsed time missing");
        require(!activity.HasMember("state"), "Repeated game-title line");
        const auto& expected_icon = input == "AzaharPlus display test" ? japanese_icon : us_icon;
        require(activity["assets"]["large_image"].GetString() == expected_icon,
                "Presence did not select the running game's artwork");
        std::cout << last_message << '\n';
    }
    system.loader.program_id = 0;
    presence.Update(true);
    rapidjson::Document unknown;
    unknown.Parse(last_message.c_str());
    require(unknown["args"]["activity"]["assets"]["large_image"].GetString() == std::string("logo"),
            "Unknown title did not fall back to the logo");
    std::cout << last_message << '\n';
    system.loader.program_id = 0x0004000000030600ULL;
    system.loader.program_available = false;
    presence.Update(true);
    rapidjson::Document unavailable;
    unavailable.Parse(last_message.c_str());
    require(unavailable["args"]["activity"]["assets"]["large_image"].GetString() == std::string("logo"),
            "Failed title-ID read did not fall back to the logo");
    std::cout << last_message << '\n';
    presence.Update(false);
    rapidjson::Document idle;
    idle.Parse(last_message.c_str());
    const auto& activity = idle["args"]["activity"];
    require(activity["name"].GetString() == std::string("AzaharPlus"), "Stale game after stopping");
    require(!activity.HasMember("details"), "Idle activity retained game details");
    require(activity["assets"]["large_image"].GetString() == std::string("logo"),
            "Idle activity retained the game image");
    std::cout << last_message << '\n';
    presence.Pause();
    rapidjson::Document cleared;
    cleared.Parse(last_message.c_str());
    require(!cleared["args"].HasMember("activity"), "Pause did not clear the activity");
}
