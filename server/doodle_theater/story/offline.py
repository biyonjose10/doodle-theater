"""Hand-written branching stories, one per theme, that star whoever the child drew.

Used when there is no AWS account (a judge running the repo locally) or the model is
unreachable, so Doodle Theater always has a show to put on. Every episode passes the
same schema check as the AI-written ones.

Placeholders: {A} first star, {B} second star (falls back to {A} when only one was drawn),
{ALL} everyone. In stage directions, who = "A" | "B" | "ALL".
"""
from __future__ import annotations

import random

N = "narrator"


def beat(text: str, *actions: tuple, speaker: str = N) -> dict:
    return {"speaker": speaker, "text": text, "actions": [
        {"who": a[0], "do": a[1], **({"at_word": a[2]} if len(a) > 2 else {})} for a in actions]}


TEMPLATES: dict[str, dict] = {
    "space": {
        "title": "{A} and the Lost Star",
        "start": ("space_station", [
            beat("Once upon a time, on a space station high above the clouds, {ALL} pressed their noses to the window.",
                 ("ALL", "enter"), ("A", "wave", "window")),
            beat("Look! A little star is falling, and it's crying all the way down!", ("A", "scared", "crying"), speaker="A"),
            beat("We have to help it, said {B}, and everybody jumped into the rocket.", ("B", "jump", "jumped")),
        ], ("Fly to the Moon", "Chase the comet")),
        "a": ("moon", [
            beat("The rocket landed softly on the Moon, where the dust was as bouncy as a trampoline.",
                 ("ALL", "jump", "bouncy")),
            beat("There was the little star, hiding behind a crater. {A} gave it the biggest hug in the galaxy.",
                 ("A", "run", "hiding"), ("A", "cheer", "hug")),
            beat("The star glowed so brightly that everyone danced all the way home. The end!",
                 ("ALL", "dance", "danced")),
        ]),
        "b": ("comet", [
            beat("Whoosh! The comet zoomed past with a sparkly tail, and the little star was riding on top.",
                 ("ALL", "run", "zoomed")),
            beat("Hold on, little star! called {B}, stretching out to catch it.", ("B", "jump", "catch"), speaker="B"),
            beat("They carried the star back to the sky, and it twinkled thank you, all night long. The end!",
                 ("ALL", "spin", "twinkled"), ("A", "wave", "night")),
        ]),
    },
    "jungle": {
        "title": "{A} and the Hidden Waterfall",
        "start": ("jungle_path", [
            beat("Deep in the green, green jungle, {ALL} heard a strange sound: splish, splash, splosh!",
                 ("ALL", "enter"), ("A", "scared", "strange")),
            beat("It sounds like a waterfall! said {A}. Let's find it!", ("A", "jump", "waterfall"), speaker="A"),
            beat("A parrot squawked from a tree. Two paths, two adventures. Which way should they go?",
                 ("B", "wave", "parrot")),
        ], ("Follow the river", "Climb to the temple")),
        "a": ("river", [
            beat("They hopped along the river stones, one, two, three, without getting their feet wet.",
                 ("ALL", "jump", "hopped")),
            beat("A family of frogs croaked a welcome song, so {B} croaked one right back!", ("B", "dance", "croaked")),
            beat("And there it was: the hidden waterfall, sparkling like a rainbow. Everyone cheered. The end!",
                 ("ALL", "cheer", "cheered")),
        ]),
        "b": ("temple", [
            beat("Up, up, up the old stone steps they climbed, puffing and giggling all the way.",
                 ("ALL", "walk", "climbed")),
            beat("Inside the temple, a sleepy monkey yawned and pointed at a secret door.", ("A", "scared", "secret")),
            beat("Behind it, the waterfall was splashing into a pool full of flowers. What a find! The end!",
                 ("ALL", "spin", "splashing"), ("A", "cheer", "find")),
        ]),
    },
    "ocean": {
        "title": "{A} Under the Sea",
        "start": ("reef", [
            beat("Down under the sea, where the fish wear stripes and spots, {ALL} went for a swim.",
                 ("ALL", "enter"), ("A", "wave", "fish")),
            beat("Bubble trouble! A little octopus has lost its favourite shell.", ("B", "scared", "trouble")),
            beat("Don't worry, said {A}. We'll find it before bedtime!", ("A", "cheer", "find"), speaker="A"),
        ], ("Explore the shipwreck", "Swim through the kelp")),
        "a": ("shipwreck", [
            beat("The old shipwreck creaked and groaned, but {ALL} were very brave.", ("ALL", "scared", "creaked")),
            beat("Inside a treasure chest, between the gold coins, the shell was shining pink.", ("A", "jump", "shining")),
            beat("The octopus was so happy it hugged everyone eight times. The end!", ("ALL", "dance", "happy")),
        ]),
        "b": ("kelp_forest", [
            beat("The kelp forest swayed like a giant green curtain, swish, swish.", ("ALL", "dance", "swayed")),
            beat("A sea turtle pointed a flipper: Look under that rock!", ("B", "run", "Look")),
            beat("There was the shell! The octopus put it on like a hat, and everyone laughed. The end!",
                 ("ALL", "cheer", "laughed"), ("A", "spin", "hat")),
        ]),
    },
    "castle": {
        "title": "{A} and the Friendly Dragon",
        "start": ("castle_gate", [
            beat("At the gates of a tall stone castle, {ALL} heard a giant sneeze. Ah-choo!",
                 ("ALL", "enter"), ("ALL", "scared", "sneeze")),
            beat("That must be the dragon, whispered {B}. Maybe it has a cold.", ("B", "wave", "dragon"), speaker="B"),
            beat("Let's help it feel better, said {A}, marching bravely through the gate.", ("A", "walk", "marching"),
                 speaker="A"),
        ], ("Ask the king", "Visit the dragon")),
        "a": ("throne_room", [
            beat("The king was sitting on his throne, eating a very large sandwich.", ("A", "wave", "king")),
            beat("A dragon with a cold? he said. It needs honey and a warm scarf!", ("B", "jump", "honey")),
            beat("They brought the dragon its scarf, and it was so happy it sneezed out fireworks. The end!",
                 ("ALL", "cheer", "fireworks")),
        ]),
        "b": ("dragon_cave", [
            beat("The dragon's cave was warm and cosy, and the dragon was wrapped in a blanket.", ("ALL", "walk", "cave")),
            beat("I'm not scary, said the dragon with a sniffle. I'm just lonely.", ("A", "scared", "scary")),
            beat("So {ALL} stayed and played games with the dragon until it smiled. The end!",
                 ("ALL", "dance", "played"), ("A", "cheer", "smiled")),
        ]),
    },
    "snow": {
        "title": "{A} and the Snow Party",
        "start": ("snowy_village", [
            beat("Snow was falling on the little village, and {ALL} were wrapped up warm.",
                 ("ALL", "enter"), ("A", "spin", "falling")),
            beat("Tonight is the Snow Party, said {A}, but we've lost the party lanterns!", ("A", "scared", "lost"),
                 speaker="A"),
            beat("A snowman pointed his carrot nose. Two places to look. Where should they go?", ("B", "wave", "snowman")),
        ], ("Search the ice cave", "Climb the mountain")),
        "a": ("ice_cave", [
            beat("The ice cave was blue and glittery, and their voices echoed: hello, hello, hello!",
                 ("ALL", "wave", "hello")),
            beat("Behind an icicle, the lanterns were glowing softly in a row.", ("B", "jump", "glowing")),
            beat("They carried them home, and the Snow Party lit up the whole night. The end!",
                 ("ALL", "dance", "party")),
        ]),
        "b": ("mountain_top", [
            beat("Up the mountain they went, crunch, crunch, crunch in the deep snow.", ("ALL", "walk", "crunch")),
            beat("At the very top, a mountain goat was wearing all the lanterns like necklaces!", ("A", "scared", "goat")),
            beat("The goat came to the party too, and danced better than anyone. The end!",
                 ("ALL", "dance", "danced"), ("B", "cheer", "anyone")),
        ]),
    },
    "dino": {
        "title": "{A} in Dinosaur Valley",
        "start": ("dino_valley", [
            beat("Stomp, stomp, stomp! {ALL} arrived in a valley full of friendly dinosaurs.",
                 ("ALL", "enter"), ("ALL", "jump", "Stomp")),
            beat("A baby dinosaur ran up, crying. Mama! I can't find my Mama!", ("B", "scared", "crying")),
            beat("We'll help you, said {A}, giving the baby a pat on the nose.", ("A", "wave", "help"), speaker="A"),
        ], ("Look by the volcano", "Check the big nest")),
        "a": ("volcano", [
            beat("The volcano rumbled, and puffs of smoke went up like grey balloons.", ("ALL", "scared", "rumbled")),
            beat("And there, warming her feet, was Mama dinosaur! She roared a happy roar.", ("A", "cheer", "roared")),
            beat("The baby ran into a big dino hug, and everybody did the stomp dance. The end!",
                 ("ALL", "dance", "dance")),
        ]),
        "b": ("nest", [
            beat("The big nest was full of eggs, wiggling and wobbling.", ("ALL", "walk", "nest")),
            beat("Crack! The eggs hatched, and out popped the baby's brothers and sisters.", ("B", "jump", "Crack")),
            beat("Mama came home to find everyone together, and gave {ALL} a dino thank-you. The end!",
                 ("ALL", "cheer", "together"), ("A", "spin", "thank")),
        ]),
    },
}


def _fill(text: str, names: dict[str, str]) -> str:
    return text.format(**names)


def episode(theme: str, cast: list[dict], seed: int | None = None) -> dict:
    """Build a playable episode for `theme` starring `cast` ([{id, name, description}])."""
    t = TEMPLATES[theme]
    rng = random.Random(seed)
    stars = cast[:]
    rng.shuffle(stars)
    a = stars[0]
    b = stars[1] if len(stars) > 1 else stars[0]
    names = {"A": a["name"], "B": b["name"],
             "ALL": stars[0]["name"] if len(stars) == 1 else
             ", ".join(s["name"] for s in stars[:-1]) + " and " + stars[-1]["name"]}
    who = {"A": [a["id"]], "B": [b["id"]], "ALL": [s["id"] for s in stars]}
    speaker_id = {"A": a["id"], "B": b["id"]}

    def scene(backdrop: str, beats: list[dict]) -> dict:
        out = []
        for bt in beats:
            text = _fill(bt["text"], names)
            acts = [{**{k: v for k, v in act.items() if k != "who"}, "who": cid}
                    for act in bt["actions"] for cid in who[act["who"]]]
            out.append({"speaker": speaker_id.get(bt["speaker"], N), "text": text, "actions": acts})
        return {"backdrop": backdrop, "beats": out}

    bd, beats, (opt_a, opt_b) = t["start"]
    start = scene(bd, beats)
    start["choice"] = {"prompt": "What should they do?",
                       "options": [{"label": opt_a, "next": "a"}, {"label": opt_b, "next": "b"}]}
    return {"title": _fill(t["title"], names), "theme": theme,
            "scenes": {"start": start, "a": scene(*t["a"]), "b": scene(*t["b"])}}
