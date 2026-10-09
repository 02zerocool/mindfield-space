# Godot — 3D Mission Memory Visualisation

The Godot integration renders your mission knowledge field as a living 3D geometry.
Ten domain clusters orbit your knowledge space: telemetry, procedures, FMEA,
propulsion, astrodynamics, life support, comms, science, regulations, planetary.

Autonomous thought bursts erupt from whichever domain is being queried.
You see your knowledge field thinking.

## Requirements

- Godot 4.3+
- Your domain stack running (`python mission/domains.py --start-all`)
- Optional: `star_point.gdshader` for glow effect (falls back to standard material)

## Setup

1. Open your Godot 4 project
2. Add `MemoryGenesis.gd` as a child Node3D in your scene
3. Set `enabled = true`
4. The domain URLs in `DOMAIN_URLS` point to `:18001–18010` by default

## Domain positions

```
telemetry     :18001   cyan     (-8,  2, -5)
procedures    :18002   white    ( 6,  3, -7)
fmea          :18003   red      ( 0,  8,  2)
propulsion    :18004   orange   (-5, -3,  8)
astrodynamics :18005   violet   ( 9, -2,  4)
life_support  :18006   green    (-7,  5,  3)
comms         :18007   sky blue ( 4, -6, -6)
science       :18008   magenta  (-3, -7, -4)
regulations   :18009   gold     ( 7,  4,  5)
planetary     :18010   brown    (-6, -5, -8)
```

## The geometry connection

When your mission knowledge field is large enough and projected via UMAP,
the topology that emerges matches the cosmic web — the same structure
your planetary science domain describes at the largest scale.

Your knowledge of the cosmos has the shape of the cosmos.
This is what you are looking at.
