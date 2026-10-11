"""Execute the real PullPacket IPC wrapper with controlled HLE results.

This is a bounded regression test, not a game/network integration test. Only
the IPC plumbing and PullPacketHLE are stubbed. The wrapper, Expected class,
and ResultStatus enum come from the selected repository source.
"""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def extract_function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--compiler", default="clang++")
parser.add_argument("--revision", help="Test a Git revision instead of the working tree")
parser.add_argument("--expect-bug", action="store_true")
parser.add_argument("--optimization", choices=["0", "2"], default="2")
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
source_path = "src/core/hle/service/nwm/nwm_uds.cpp"
source = (
    subprocess.check_output(["git", "show", f"{args.revision}:{source_path}"], cwd=repo, text=True)
    if args.revision
    else (repo / source_path).read_text(encoding="utf-8")
)
header_path = "src/core/hle/service/nwm/nwm_uds.h"
header = (
    subprocess.check_output(["git", "show", f"{args.revision}:{header_path}"], cwd=repo, text=True)
    if args.revision
    else (repo / header_path).read_text(encoding="utf-8")
)
result_enum = re.search(r"enum class ResultStatus \{.*?\n\};", header, re.S).group()
wrapper = extract_function(source, "void NWM_UDS::PullPacket(Kernel::HLERequestContext& ctx)")
prefix = r'''
#include <algorithm>
#include <compare>
#include <cstdint>
#include <iostream>
#include <memory>
#include <new>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>
#include "common/expected.h"
using u8 = uint8_t;
using u16 = uint16_t;
using u32 = uint32_t;
#define LOG_DEBUG(...) ((void)0)
enum class ErrorDescription { NotAuthorized = 1002, TooLarge = 1001 };
enum class ErrorModule { UDS };
enum class ErrorSummary { InvalidState, WrongArgument };
enum class ErrorLevel { Status, Usage };
struct Result {
    u32 value;
    Result(ErrorDescription d, ErrorModule, ErrorSummary, ErrorLevel) : value(u32(d)) {}
};
constexpr u32 ResultSuccess = 0;
struct SecureDataHeader { u16 src_node_id; };
namespace Kernel {
struct HLERequestContext {
    std::vector<u32> request{1, 370, 1478};
    std::vector<u32> response;
    std::vector<u8> buffer;
};
}
namespace IPC {
struct RequestBuilder {
    Kernel::HLERequestContext& ctx;
    void Push(Result v) { ctx.response.push_back(v.value); }
    template <class T> void Push(T v) { ctx.response.push_back(u32(v)); }
    void PushStaticBuffer(std::vector<u8> v, int) { ctx.buffer = std::move(v); }
};
struct RequestParser {
    Kernel::HLERequestContext& ctx;
    size_t index{};
    explicit RequestParser(Kernel::HLERequestContext& c) : ctx(c) {}
    template <class T> T Pop() { return T(ctx.request.at(index++)); }
    RequestBuilder MakeBuilder(int, int) { return {ctx}; }
};
}
'''
fixture = r'''
struct NWM_UDS {
    Common::Expected<int, ResultStatus> next;
    explicit NWM_UDS(Common::Expected<int, ResultStatus> value) : next(value) {}
    Common::Expected<int, ResultStatus> PullPacketHLE(u32, u32, u32,
                                                    std::vector<u8>& buffer, void* out) {
        if (next && *next > 0) {
            buffer.assign(*next, 0xA5);
            static_cast<SecureDataHeader*>(out)->src_node_id = 2;
        }
        return next;
    }
    void PullPacket(Kernel::HLERequestContext&);
};
'''
main = r'''
int main(int argc, char**) {
    const bool expect_bug = argc > 1;
    std::vector<int> failures;
    // Cover every legal payload length, especially enum values 9, 10 and 11.
    for (int size = 0; size <= 0x5C6; ++size) {
        NWM_UDS uds{size};
        Kernel::HLERequestContext ctx;
        uds.PullPacket(ctx);
        const bool ok = ctx.response.size() == 3 && ctx.response[0] == 0 &&
                        ctx.response[1] == u32(size) && ctx.buffer.size() == size &&
                        (expect_bug || size != 0 || ctx.response[2] == 0) &&
                        std::all_of(ctx.buffer.begin(), ctx.buffer.end(),
                                    [](u8 b) { return b == 0xA5; });
        if (!ok) {
            failures.push_back(size);
            std::cout << "success length=" << size << " misclassified result="
                      << ctx.response.at(0) << '\n';
        }
    }
    int bad_errors = 0;
    for (auto error : {ResultStatus::RecvError_NotConnected, ResultStatus::RecvError_BadNode,
                       ResultStatus::RecvError_PacketSizeTooLarge}) {
        NWM_UDS uds{Common::Unexpected(error)};
        Kernel::HLERequestContext ctx;
        uds.PullPacket(ctx);
        const u32 expected = error == ResultStatus::RecvError_PacketSizeTooLarge ? 1001 : 1002;
        if (ctx.response.size() != 1 || ctx.response[0] != expected || !ctx.buffer.empty()) {
            ++bad_errors;
        }
    }
    std::cout << "payload_lengths=1479 misclassified=" << failures.size()
              << " true_error_cases=3 true_error_mismatches=" << bad_errors << '\n';
    return bad_errors || (expect_bug ? failures != std::vector<int>{9, 10, 11}
                                    : !failures.empty());
}
'''
with tempfile.TemporaryDirectory(prefix="uds-pull-regression-") as work:
    cpp = Path(work) / "pull_packet.cpp"
    exe = Path(work) / "pull_packet.exe"
    cpp.write_text(prefix + result_enum + fixture + wrapper + main, encoding="utf-8")
    subprocess.run(
        [args.compiler, "-std=c++20", f"-O{args.optimization}", "-I", str(repo / "src"),
         str(cpp), "-o", str(exe)], check=True
    )
    subprocess.run([str(exe)] + (["expect-bug"] if args.expect_bug else []), check=True)
