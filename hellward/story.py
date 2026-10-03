"""The campaign's story: every page, what its painted panel shows, and the people and things the panels share.

A page is one painted panel (``godot/game/assets/story/<key>.jpg``, which the client shows) and a few paragraphs. A location has a page
before its first fight and one after its first victory; each act's last fight has no after page, since the act's
ending takes its place. The prologue is the intro comic (``godot/game/assets/story/prologue``) and is not here.
``docs/story.md`` keeps the rules the words follow and the panel bible that :data:`REFERENCES`, :data:`STYLES`
and each :class:`Page` put into the painter's prompt (``tools/story.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

REFERENCES: dict[str, str] = {
    "you": "the keeper: a hooded figure in a dark travelling cloak, always seen from behind or in shadow, holding up a "
           "brass lantern with a single red flame",
    "akara": "Akara: an old priestess of the Sisterhood in a grey hooded robe with a silver-grey veil, carrying one "
             "tall white candle",
    "priest": "the Bone Priest: a skeleton in a ragged brown hooded cassock, a gold crown with violet-tipped spikes on "
              "his bare skull, small green lights in his eye sockets, a crimson stole embroidered with a gold cross, a "
              "tall bone staff topped by a caged green orb",
    "necromancer": "the necromancer: a pale, white-haired young man in close-fitting armour of bleached bone plates "
                   "over black cloth, a curved ivory dagger at his belt, calm and exact",
    "druid": "the eldest druid: a tall old man with a grey braided beard, a cloak of living bark and leaves, a staff of "
             "black oak crowned with antlers",
    "lamp": "the lamp of Tristram: a heavy lamp of deep ruby-red glass in a pierced gilded brass cage shaped like a "
            "small cathedral spire, hanging on three long chains, one red flame inside",
    "mother_lamp": "the mother lamp: a great lamp of clear golden glass the size of a man in a gilt cage of many "
                   "spires, hanging on heavy gold chains, one tall gold flame inside",
    "seal": "the cathedral's seal: a gold cross set inside the outline of a hanging lamp",
}

STYLES: dict[int, str] = {
    1: "A full-bleed painting in the style of a gothic horror graphic novel: heavy black ink shadows over most of the frame, bold brush contours, "
       "flat muted colours of bone, rust and dried-blood crimson, lit only by the lights the description names; rough "
       "paper grain.",
    2: "A full-bleed painting in the style of a gothic horror graphic novel: heavy black ink shadows over most of the frame, bold brush contours, "
       "flat muted colours of moss green, black water, tarnished gilt and torchlight, lit only by the lights the "
       "description names; rough paper grain.",
}

RULES = ("Nothing glows unless the description says so: no glowing eyes, no magic swirls. No text, letters, writing or "
         "speech bubbles. No border, frame, margin or paper edge: the painting fills the whole picture to every edge.")
FRAMING = ("Keep the designs of the reference images, redrawn in this ink style. The lower quarter of the frame falls "
           "into black shadow; the subject sits in the upper three quarters.")


@dataclass(frozen=True)
class Page:
    key: str                     # its panel's picture, godot/game/assets/story/<key>.jpg
    panel: str                   # what the panel shows, for the painter
    text: tuple[str, ...]        # the paragraphs
    refs: tuple[str, ...] = ()   # names in REFERENCES: the figures and objects it shows
    base: str = ""               # a prologue panel to paint this one as an edit of, keeping its framing


@dataclass(frozen=True)
class Story:
    key: str                     # "tristram/before", "act1/end", ...
    act: int
    pages: tuple[Page, ...]


def _page(key: str, panel: str, *text: str, refs: tuple[str, ...] = (), base: str = "") -> tuple[Page, ...]:
    return (Page(key, panel, text, refs, base),)


STORIES: dict[str, Story] = {s.key: s for s in (
    # -- Act I, The Descent -------------------------------------------------------------------------
    Story("tristram/before", 1, _page(
        "tristram-before",
        "A village burning at night; small red-skinned Fallen demons pour out of cellar doors with knives and torches. "
        "In the foreground, seen from behind at the village well, the keeper holds up the lantern.",
        "The lamp guttered at midnight, and now Tristram burns. The Fallen come up through the cellars with knives and "
        "torches, red southern knives among them, and behind them walk the village dead, still in their Sunday clothes.",
        "Akara finds you at the well. From her candle she lights your lantern — one flame of the lamp's own. "
        "\"The old towers answer whoever keeps the lamp,\" she says. \"Wake what sleeps, and raise where nothing sleeps. "
        "Keep it tonight. Ask me your questions at dawn.\"",
        refs=("you",))),
    Story("tristram/after", 1, _page(
        "tristram-after",
        "Grey dawn over the ashes of the village; in the upper middle of the frame, a hand holds up a small finger bone "
        "carved with the cathedral's seal.",
        "Dawn came grey over the ashes. Akara turned the dead shaman's charms over, one by one, and held up a finger "
        "bone carved with the cathedral's seal. \"You asked at the well,\" she said. \"Here is your answer. It was a "
        "priest's gift.",
        "The Fallen had not come on their own. Someone had sent them up from the churchyard.",
        refs=("seal",))),
    Story("graveyard/before", 1, _page(
        "graveyard-before",
        "A churchyard at night, its gate hanging open and every grave dug out; skeletons climb from the earth. Among "
        "the headstones stands the Bone Priest, still, watching; hooded acolytes raise their hands over the graves.",
        "The churchyard gate stands open and every grave is empty. The Bone Priest stands among the stones while his "
        "acolytes call the buried by name. He christened most of them. He buried all of them.",
        "Last night you dreamed the nave: a torn carpet, dark arches, the lamp high above.",
        "One crypt is still sealed. Its gold is yours if you break the seal — and whatever walks out with it.",
        refs=("priest",))),
    Story("graveyard/after", 1, _page(
        "graveyard-after",
        "A crypt wall covered from floor to vault in scratched tally marks, row on row, and beside each mark a tiny "
        "snuffed lamp; Akara's candle lights it from the side.",
        "On the crypt wall someone had scratched a tally, row on row, too many to count, and beside every mark the "
        "same small sign: a lamp, snuffed.",
        "Akara held her candle to it. \"Every night he has cast his bones and watched this fight,\" she said. \"In "
        "every night he has seen, the lamp goes out.\"",
        refs=("akara",))),
    Story("cathedral/before", 1, _page(
        "cathedral-before",
        "A gothic nave: a torn red carpet down the aisle, horned goatmen kneeling in the pews, a Blood Witch in red "
        "singing from the pulpit; high above, the red lamp.",
        "The nave is as you dreamed it: the torn carpet, the arches, the lamp high above. But the goatmen have "
        "come down from the hills to kneel in the pews, and a Blood Witch sings vespers from the pulpit.",
        "The priest has invited guests.",
        refs=("lamp",))),
    Story("cathedral/after", 1, _page(
        "cathedral-after",
        "Behind a stone altar, a narrow stair goes down into darkness; on its first step, a guttering candle stub.",
        "The lamp still burned. Beneath the altar a stair you had never seen went down into cold air, and on the altar "
        "above it stood a candle stub, still warm.",
        "He had gone down ahead of you, unhurried, the way a priest goes down to a funeral.")),
    Story("catacombs/before", 1, _page(
        "catacombs-before",
        "Halls of skulls and bones stacked to the vaulted ceiling, bones sliding loose; at the far end a huge armoured "
        "Overlord breaks through a barred door.",
        "Under the cathedral lie nine hundred years of the faithful, stacked to the ceiling. Tonight they are "
        "unstacking themselves.",
        "The Overlords came up from the deep below, nearer the door. The priest unbarred the old crypt doors for them, "
        "and taught them to break the new ones.",
        refs=())),
    Story("catacombs/after", 1, _page(
        "catacombs-after",
        "A bare stone cell with a cot and a cold black lamp, long unlit; on the floor, violet-glowing bones laid end to "
        "end as a long winding path, and its last stretch bare stone. No other light.",
        "In the deepest ossuary you found his cell: a cot, a cold lamp, and his bones, laid out on the floor as a "
        "winding path through every room you have fought in.",
        "Its last stretch was bare. It led to the door.")),
    Story("caves/before", 1, _page(
        "caves-before",
        "A vast cavern lit red from below by a lava lake; stone gargoyles hang from the vault like bats; at the edge "
        "of the light, Akara turns back with her candle.",
        "The catacombs open onto a cavern lit from below. Lava crawls across its floor, and gargoyles hang in the "
        "vault, waiting for the heat to lift them.",
        "Akara will go no further. \"Someone must keep the lamp while you are below,\" she says. \"Past the lava is "
        "the door the saints built on, and he is waiting at it.\"",
        refs=("akara",))),
    Story("caves/after", 1, _page(
        "caves-after",
        "Steps cut into black rock at the edge of a lava flow, each step worn into a deep hollow by feet; red light "
        "from below.",
        "At the lava's edge the rock had been cut into steps, and the steps were worn into hollows by one pair of "
        "feet.",
        "Every night for nine hundred years the keeper came down here and cast his bones before the door, and every "
        "night they showed the lamp going out. Somewhere in those years he stopped keeping it, and began to wait.")),
    Story("hells_gate/before", 1, _page(
        "hells_gate-before",
        "A colossal door in the rock, firmly shut except for a single hand's-width crack; hellfire blazing through that "
        "thin crack with a vast horned shape inside the fire; at the threshold, the Bone Priest turns toward the viewer.",
        "The door the saints built on stands open a hand's width. Through the gap you see fire, and the shape of "
        "Azazel the Flayer.",
        "The Bone Priest waits at the threshold, crowned, and turns to face you. \"Nine hundred years I kept your "
        "saints' lamp,\" he says. \"I promised him this hour. Tonight I let it go out.\"",
        refs=("priest",))),
    Story("act1/end", 1, (
        Page("act1-end-1",
             "The Bone Priest kneels on a threshold casting violet-glowing bones onto the stone, again and again; "
             "behind him, out of focus, a colossal door shut.",
             ("Azazel fell in the doorway, and the door swung shut on him.",
              "The Bone Priest cast his bones on the threshold, again and again. They showed him every stone, every "
              "tower, every demon, as they always had. They had never once shown him you.",
              "The nearer door shut against him; he stepped back into the dark and went east. Above you, the lamp of "
             "Tristram burned."),
             ("priest",)),
        Page("act1-end-2",
             "The same stained-glass window: the saints now light many small red lamps from one great golden flame "
             "held high in the middle of the glass.",
             ("The saints lit a lamp over every door to hell, and they lit every one from a single flame: the mother "
              "lamp, in the Temple of Light at Kurast, across the sea.",
              "If the mother lamp goes out, every lamp lit from it goes out with it. Tristram's too."),
             base="glass"),
        Page("act1-end-3",
             "A night harbour; far out, a ship with black sails leaves under the moon. On the quay, seen from behind, "
             "the keeper holds up the lantern, and Akara stands beside him with her candle.",
             ("A ship left the coast last night with one passenger and no crew, sailing east.",
              "\"Go,\" said Akara. \"I will keep this one. Take its flame, and the old towers will know you.\" You held "
              "the lantern to the lamp until its flame stood straight, and went down to the sea, where a boat waited."),
             ("you", "akara")),
    )),
    # -- Act II, The Drowned Temples ----------------------------------------------------------------
    Story("docks/before", 2, _page(
        "docks-before",
        "On a harbour wall stands the necromancer, looking down at the viewer, his armour yellowed bone: a ribbed "
        "cuirass, knuckle-ridged pauldrons, matte and porous, clearly bone and never metal; on the far piers behind him, "
        "tiny distant red Flayers wait; a swamp city of gold roofs and rotting wooden piers rises in tiers.",
        "Kurast rises out of the swamp in tiers of gold and rotting wood. The harbour is empty of pilgrims. Along the "
        "piers the Flayers are waiting, and their shaman is already singing.",
        "A pale man in bone armour watches you land. \"I am a priest of Rathma,\" he says. \"Your enemy stole our "
        "art. Let me lend it back to you as the Bone Altar.\"",
        refs=("necromancer",))),
    Story("docks/after", 2, _page(
        "docks-after",
        "The necromancer kneels on a wet pier among small dead jungle fiends, closing their eyes with two fingers.",
        "The shaman's song stopped. The necromancer knelt among the Flayers and closed their eyes. \"Twice his shaman "
        "raised them on the priest's stolen art,\" he said. \"Each time, fewer of them came back.",
        "\"He is not raising an army. He is spending one.\"",
        "\"And his bones will never show him you. They show all that is settled — every stone, every tower, every "
        "demon. They cannot show the light itself.\"",
        refs=("necromancer",))),
    Story("spider_forest/before", 2, _page(
        "spider_forest-before",
        "In a clearing, a ring of enormous ancient oaks; the eldest druid stands at its heart; behind him, webs hang "
        "between the trees like grey sails.",
        "The road to the temples runs through a forest the spiders own. Webs hang between the trees like sails, and at "
        "dusk the bats pour out of them.",
        "In a clearing stands a ring of oaks older than Kurast. \"The trees remember the saints who lit the lamps,\" "
        "says the eldest druid. \"They will stand with you, if you stand close to them.\"",
        refs=("druid",))),
    Story("spider_forest/after", 2, _page(
        "spider_forest-after",
        "The oak ring at dawn, roots closing over the bodies of giant spiders; the eldest druid points east toward black "
        "water.",
        "The grove held. Where the spiders fell, the oaks were already putting down roots.",
        "The eldest druid pointed east, to where the jungle turns to black water. \"He passed here three nights ago. "
        "The oaks remember the lamps being lit — and they do not like him.\"",
        refs=("druid",))),
    Story("jungle/before", 2, _page(
        "jungle-before",
        "A jungle path under green gloom; zealots in white and gold march in file; an inquisitor raises a hand, and a "
        "violet rune circle burns on the ground ahead of him.",
        "The jungle closes over the path. Zealots of the fallen Zakarum church march through it in white and gold, and "
        "their inquisitors curse without a word of prayer.",
        "There will be no chant to warn you — only the mark, long before the curse falls. Read the ground, and kill "
        "the silent ones first.",
        refs=())),
    Story("jungle/after", 2, _page(
        "jungle-after",
        "A gloved hand holds a folded letter; its wax seal, stamped with the cathedral's seal, is broken.",
        "Among the inquisitors' dead you found the seal of the High Council, and a letter in the Bone Priest's hand: "
        "Your lamp gutters, as mine did. Let me keep it for you.",
        "The Council let him in.",
        refs=("seal",))),
    Story("drowned_city/before", 2, _page(
        "drowned_city-before",
        "Half-sunken temples and streets turned to canals; a huge Thorned Hulk, overgrown with thorns and weed, wades "
        "out of the black water.",
        "Half of Kurast has sunk into the swamp. Its streets are canals and its temples islands, and something huge "
        "walks the flooded avenues: the Thorned Hulks, grown out of the drowned.",
        "They go through a warded gate the way a man goes through a curtain.",
        refs=())),
    Story("drowned_city/after", 2, _page(
        "drowned_city-after",
        "A flooded shrine; the water glows warm red; the necromancer lifts wet fingers to his lips.",
        "In a flooded shrine the water was warm and red. The necromancer tasted it and spat. \"Lamp oil,\" he said. "
        "\"The mother lamp's.",
        "\"He is not putting it out. He is draining it, a little each night, so the city will not notice until it is "
        "dark.\"",
        refs=("necromancer",))),
    Story("travincal/before", 2, _page(
        "travincal-before",
        "A temple terrace at night; a row of elders in gold robes stands facing the viewer, each holding a violet curse "
        "glowing in his hand; high above them hangs the mother lamp, dim.",
        "The High Council meets on the temple terrace under the mother lamp: a row of elders in gold, and every one of "
        "them curses.",
        "They have waited for you. The Bone Priest has told them how this night ends. He promised Azazel an hour too, "
        "and Azazel is dust in a shut door.",
        refs=("mother_lamp",))),
    Story("travincal/after", 2, _page(
        "travincal-after",
        "Great temple doors nearly closed on their own, only a hand's-width gap remaining between them; through that "
        "thin gap, the mother lamp sunk to a red ember in dark glass and the glint of violet light on a gold floor. No "
        "candles, no other light.",
        "The last elder fell on the temple stairs. Above them the mother lamp hung dim and red, its oil almost gone. "
        "The temple doors swung shut by themselves.",
        "Behind them, on the temple floor, you could hear bones being cast, again and again.",
        "Behind you, up the temple road, the eldest druid was coming with his flask of oil.",
        refs=("mother_lamp",))),
    Story("temple/before", 2, _page(
        "temple-before",
        "A vast golden temple interior gone almost dark; the mother lamp hangs over the altar with its flame sunk to a "
        "last red ember, the great glass nearly black; beneath it the Bone Priest, grown huge, bones in his open hand, "
        "violet fire around him. No candles, no other light.",
        "Under the mother lamp the Bone Priest waits, and for the first time he will fight you himself.",
        "\"Every night since Tristram I have cast these bones,\" he says. \"They show me every stone of this "
        "temple, every demon in it, every tower you will build. They have never shown me you. So I have come to "
        "look.\"",
        refs=("priest", "mother_lamp"))),
    Story("act2/end", 2, (
        Page("act2-end-1",
             "Violet bones scattered across a gold floor; above them a ghostly vision in gold light: a shadow with a "
             "lantern standing beside a burning lamp.",
             ("The bones fell from his hand and scattered across the gold floor, and above them, for the first time, "
              "the vision held you: a shadow with a lantern, and the lamp still burning.",
              "\"There you are,\" he said, and was dust."),
             ("you",), base="bones"),
        Page("act2-end-2",
             "A vast dark temple; the mother lamp hangs cold and black; the only light is the keeper's small red "
             "lantern, seen from behind.",
             ("When he was dust, the mother lamp guttered and went out, and the temple was dark but for your "
              "lantern — which burns on keeping, not oil.",),
             ("you", "mother_lamp")),
        Page("act2-end-3",
             "The keeper holds the lantern up to the great lamp while the eldest druid pours oil from a wooden flask; "
             "the mother flame catches and rises gold, lighting the whole temple.",
             ("You held it up to the great lamp: Tristram's flame, lit from this one nine hundred years ago. The eldest "
              "druid poured oil pressed from the grove's oaks, and the mother flame caught, and rose gold.",),
             ("you", "druid", "mother_lamp")),
        Page("act2-end-4",
             "Dawn through tall cathedral windows; the red lamp of Tristram burns straight; Akara looks up at it from "
             "below with her candle.",
             ("Across the sea, in a cathedral built on a door to hell, Akara watched a small red flame stand straight "
              "again.",
              "Keep it burning."),
             ("akara", "lamp")),
    )),
)}

LAST_PAGES = {1: "act1/end", 2: "act2/end"}   # what each act's last victory opens, in place of an after page
