from __future__ import annotations


TAG_SUGGESTIONS = [
    "生存",
    "生存合作",
    "生存建造",
    "开放世界生存",
    "合作",
    "双人合作",
    "派对合作",
    "社交合作",
    "合作射击",
    "动作",
    "动作冒险",
    "动作 Roguelike",
    "冒险",
    "独立",
    "角色扮演",
    "在线角色扮演",
    "大型多人在线",
    "策略",
    "多人策略",
    "竞技",
    "竞技射击",
    "战术合作",
    "格斗",
    "派对",
    "休闲",
    "模拟",
    "体育",
    "抢先体验",
]


ALIASES = {
    "生存": ["生存", "生存合作", "生存多人", "多人开放世界生存", "开放世界生存", "生存建造"],
    "建造": ["建造", "生存建造", "开放世界生存", "沙盒", "工程沙盒"],
    "合作": ["合作", "在线合作", "双人合作", "派对合作", "合作射击", "合作狩猎", "合作动作射击"],
    "开黑": ["合作", "多人", "派对合作", "社交合作", "合作射击"],
    "射击": ["射击", "合作射击", "竞技射击", "团队射击", "战术合作"],
    "fps": ["射击", "合作射击", "竞技射击", "团队射击", "战术合作", "动作"],
    "FPS": ["射击", "合作射击", "竞技射击", "团队射击", "战术合作", "动作"],
    "策略": ["策略", "多人策略"],
    "rpg": ["角色扮演", "在线角色扮演", "大型多人在线"],
    "RPG": ["角色扮演", "在线角色扮演", "大型多人在线"],
    "派对": ["派对", "派对合作", "派对闯关", "社交合作", "社交推理"],
    "休闲": ["休闲", "轻松合作", "派对合作"],
    "竞技": ["竞技", "竞技多人", "竞技射击", "格斗对战", "近战大逃杀"],
    "格斗": ["格斗", "格斗对战", "平台格斗"],
    "mmorpg": ["大型多人在线", "在线角色扮演", "角色扮演"],
    "MMORPG": ["大型多人在线", "在线角色扮演", "角色扮演"],
}


def expand_user_terms(terms: list[str]) -> set[str]:
    expanded: set[str] = set()
    for term in terms:
        cleaned = term.strip()
        if not cleaned:
            continue
        expanded.add(cleaned.lower())
        for alias in ALIASES.get(cleaned, []):
            expanded.add(alias.lower())
    return expanded


def term_matches(value: str, terms: set[str]) -> bool:
    lowered = value.lower()
    return any(term in lowered or lowered in term for term in terms)
