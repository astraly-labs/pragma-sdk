import random

HumanReadableId = str

ADJECTIVES = [
    "brave",
    "calm",
    "delightful",
    "eager",
    "fancy",
    "gentle",
    "happy",
    "jolly",
    "kind",
    "lively",
    "merry",
    "nice",
    "proud",
    "quick",
    "silly",
    "tender",
    "unique",
    "victorious",
    "witty",
    "zany",
]

NOUNS = [
    "lion",
    "tiger",
    "bear",
    "eagle",
    "shark",
    "panther",
    "leopard",
    "wolf",
    "falcon",
    "dragon",
    "unicorn",
    "phoenix",
    "griffin",
    "raven",
    "orca",
    "dolphin",
    "hawk",
    "lynx",
    "cougar",
    "stallion",
]


def generate_human_readable_id() -> HumanReadableId:
    adjective = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    number = random.randint(1, 99)
    return f"{adjective}-{noun}-{number:02}"
