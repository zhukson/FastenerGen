"""
GB (Chinese National Standard) drawing standards for DXF output.

Defines layer names, colors, line types, dimension styles, and text styles
per GB/T 4458 (mechanical drawing) and GB/T 1182 (geometric tolerances).

Implemented in Session 4.
"""

# Layer definitions: (name, color_index, linetype)
LAYERS: list[tuple[str, int, str]] = [
    ("0", 7, "CONTINUOUS"),
    ("OUTLINE", 7, "CONTINUOUS"),        # Visible edges
    ("HIDDEN", 3, "DASHED"),             # Hidden edges
    ("CENTER", 1, "CENTER"),             # Center lines
    ("DIMENSION", 2, "CONTINUOUS"),      # Dimensions
    ("ANNOTATION", 5, "CONTINUOUS"),     # Text notes
    ("TITLE_BLOCK", 7, "CONTINUOUS"),    # Title block
    ("SECTION", 6, "CONTINUOUS"),        # Section lines
    ("HATCH", 4, "CONTINUOUS"),          # Cross-hatching
]

# Standard drawing scales
SCALES: list[str] = ["1:1", "1:2", "1:5", "2:1", "5:1"]

# Die steel grades commonly used in cold heading tooling
DIE_STEEL_GRADES: list[str] = [
    "SKD11",     # D2 equivalent — general purpose
    "DC53",      # Improved D2 — better toughness
    "ASP2030",   # Powder metallurgy HSS — high wear resistance
    "SKH51",     # M2 HSS — high speed punches
    "Cr12MoV",   # Chinese equivalent of D2
    "W6Mo5Cr4V2",  # Chinese M2 equivalent
    "YG15",      # Cemented carbide — extreme wear resistance
    "YG20",      # Cemented carbide — tougher grade
]

# Surface treatment options
SURFACE_TREATMENTS: list[str] = [
    "TiN",       # Titanium Nitride — gold color, good wear resistance
    "TiCN",      # Titanium Carbonitride — better than TiN
    "TiAlN",     # Titanium Aluminum Nitride — high temperature
    "DLC",       # Diamond-Like Carbon — very hard
    "none",      # No coating
]
