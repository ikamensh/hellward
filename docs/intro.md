# Hellward — the intro

A story of under a minute told twice, once as generated video and once as painted panels with
captions, so the two ways of telling it can be compared. Same words, same voice, same score.
`tools/intro.py` makes both; the shots and panels, their prompts and their lines are the table
at its top.

## The idea

The game's one new thing is an enemy that thinks: a leader plays the fight ahead in its head and
then picks the tower, the curse and the moment. The intro is that enemy talking to you. The voice
that tells the cathedral's legend turns out to be the Bone Priest, who was once this cathedral's
priest and kept its lamp. It knows the house, and it has already watched the fight many times.

Every detail points at something the player will meet in the game:

| In the intro | In the game |
|---|---|
| the lamp that keeps hell's door shut | the red orb: each demon that reaches the sanctuary dims it |
| hell tears open at the end of the pilgrims' carpet | the portal and the crimson carpet the monsters walk |
| "Its fire. Its thunder. Its frost. And its dead." | the four towers: Pyre, Storm Obelisk, Frost Shrine, Plague Totem |
| the priest's red stole with its gold cross | the Bone Priest's painted sprite |
| he casts the bones and sees the fight before it begins | the leaders' rollouts, the chronicle and the leaders' minds |
| "which tower to break. And when." | a leader chooses the tower, the curse and when to cast |
| a cage of bones closes round the Pyre as demons batter a gate | Bone Prison, warded gates, violet as the colour of curses |
| the bell, the ponder breath, the leak gong | the game's own cues |
| "In every night I have seen, the lamp goes out." | the goal, given as a dare: keep it burning |

## The script

Spoken by the Bone Priest: old, dry, unhurried, sure of himself. The first line says "your
saints", not "our": the narrator is not on your side, and a second viewing hears it.

| # | Picture | Line |
|---|---|---|
| 1 | A stained-glass window: saints over a burning pit of demons, the red lamp hanging above. | Your saints built this cathedral on the door to hell... |
| 2 | The lamp itself, its flame small and bent. The line runs over the cut, so the lamp appears on its words. | ...and lit a lamp, to keep it shut. Nine hundred years, it burned. Tonight... it gutters. |
| 3 | The nave floor at the carpet's end splits into a red vortex; the horde climbs out. | *(no words: a roar)* |
| 4 | Four towers wake one after another. | So you wake what the old house still holds. Its fire. Its thunder. Its frost. And its dead. |
| 5 | Among the running horde one figure stands still and looks at you: the Bone Priest. | I know this house. I kept its lamp, once. |
| 6 | Bones thrown on the flagstones fall into the shape of the nave; ghostly towers flicker over them, one future after another. | Now I cast the bones, and watch the fight a hundred times before it begins. |
| 7 | Demons batter a warded gate under the Pyre's fire; a violet beam, and a cage of bones closes round the Pyre. | I know which tower to break. And when. |
| 8 | The lamp again. The flame shrinks to an ember under a skeletal hand's shadow, and goes out. | In every night I have seen, the lamp goes out. |
| 9 | Black. A spark catches in the lamp. **HELLWARD**. | *Keep it burning.* (written, not spoken) |

The voice is xAI's `leo`, the most human-sounding of its nineteen male voices, so the twist holds
until he names himself. From "I know this house" on, an octave-down copy of the voice runs quietly
under it: the mask slips.

## How it is made

```bash
OUT=~/saga/evidence/hellward/intro
uv run python tools/intro.py paint $OUT     # the lamp and priest references, 16 film keyframes, 15 comic panels
uv run python tools/intro.py voice $OUT     # three takes a line, Gemini picks one by listening; the timeline
uv run python tools/intro.py animate $OUT   # the film's clips (Grok Imagine Video 1.5, 1080p)
uv run python tools/intro.py score $OUT     # the music (Lyria 3)
uv run python tools/intro.py cut $OUT       # intro-film.mp4 and intro-comic.mp4, 53 s each
```

The pictures come from Gemini 3 Pro Image, given the title painting, the Bone Priest's sprite and the
tower sheet as references, so the designs match the game. The comic is painted in a heavy-ink
graphic-novel style; the film keyframes follow the title painting. The sound is the game's own
cues (the wave bell, the ponder breath, the curse, the leak gong, cleanse), so the intro teaches the
game's sounds.

**Cost, 2026-09-25:** about $12 for eight 1080p clips ($0.25/s; 720p is $0.08/s), about $6 for the
pictures, under $1 for the voice, the music and the listening. The xAI credit ran out before the four
1.7 s tower shots, so in the film those play their dark and lit keyframes as a flare. `animate` makes
them once there is credit.

## Film or comic

Gemini watched both cuts: the comic 8/10, the film 3/10. The film's clips have the usual generated-video
faults in motion: demons sliding rather than running, the priest's crowd morphing, pink rings appearing
around him after two seconds (the cut uses the first two seconds at half speed). Its best shots (the
breach, the bones, the hand closing over the lamp) are strong, and each costs money and luck to redo.

The comic costs a few cents a panel, can be repainted one panel at a time, has no motion to go wrong
and keeps the painted style exactly. It is also the one the game can play itself: stills, a slow pan,
captions and the soundtrack, without shipping 80 MB of video.

Lyria ignores timestamps in its prompt (it swelled steadily for 67 s), so the cut fades the music
where the lamp goes out. Music that must hit marks would come from the game's own synthesiser.
