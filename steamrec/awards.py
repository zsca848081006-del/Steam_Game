from __future__ import annotations


# Initial curated Steam-available subset of recent The Game Awards winners and
# nominees that are relevant to group/multiplayer discovery. Console-only titles
# are intentionally omitted because this app recommends Steam games.
TGA_MULTIPLAYER_MARKS: dict[int, list[str]] = {
    553850: ["TGA 2024 最佳多人游戏获奖"],
    1938090: ["TGA 2024 最佳多人游戏提名"],
    1778820: ["TGA 2024 最佳多人游戏提名"],
    2183900: ["TGA 2024 最佳多人游戏提名"],
    1086940: ["TGA 2023 年度游戏", "TGA 2023 最佳多人游戏获奖"],
    1260320: ["TGA 2023 最佳多人游戏提名"],
    1364780: ["TGA 2023 最佳多人游戏提名"],
    1818750: ["TGA 2022 最佳多人游戏提名"],
    1361510: ["TGA 2022 最佳多人游戏提名"],
    1426210: ["TGA 2021 年度游戏", "TGA 2021 最佳多人游戏获奖"],
    924970: ["TGA 2021 最佳多人游戏提名"],
    1446780: ["TGA 2021 最佳多人游戏提名"],
    1063730: ["TGA 2021 最佳多人游戏提名"],
    892970: ["TGA 2021 最佳多人游戏提名"],
    945360: ["TGA 2020 最佳多人游戏获奖"],
    1097150: ["TGA 2020 最佳多人游戏提名"],
    1245620: ["TGA 2022 年度游戏"],
}
