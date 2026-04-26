"""Benchmark protocol cases used by comparison and ablation scripts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProtocolCase:
    case_id: str
    protocol_class: str
    text: str


CASES = [
    ProtocolCase(
        "pcr_8_sample",
        "PCR setup",
        """
PCR Master Mix Setup

Materials:
- DNA template samples
- PCR master mix

Steps:
1. Prepare 8 samples in a 96-well PCR plate.
2. Add 10 uL of DNA template to the corresponding sample well.
3. Add 40 uL of PCR master mix to each well.
4. Mix gently by pipetting up and down 3 times.
5. Keep the plate on ice until thermal cycling.
""",
    ),
    ProtocolCase(
        "qpcr_12_sample",
        "qPCR setup",
        """
qPCR Reaction Setup

Materials:
- DNA template samples
- qPCR master mix
- nuclease-free water

Steps:
1. Prepare 12 qPCR reactions in a 96-well optical plate.
2. Add 5 uL DNA template to each reaction well.
3. Add 15 uL qPCR master mix to each reaction well.
4. Add 5 uL nuclease-free water to each well.
5. Mix each reaction gently 3 times.
""",
    ),
    ProtocolCase(
        "elisa_plate_setup",
        "ELISA plate setup",
        """
ELISA Plate Liquid Handling

Materials:
- diluted serum samples
- assay buffer
- enzyme conjugate

Steps:
1. Prepare 8 ELISA wells in a 96-well plate.
2. Add 50 uL diluted serum sample to each assigned well.
3. Add 50 uL assay buffer to each well.
4. Add 20 uL enzyme conjugate to each well.
5. Mix gently after each addition.
""",
    ),
    ProtocolCase(
        "dna_cleanup_plate",
        "DNA cleanup setup",
        """
DNA Cleanup Binding Setup

Materials:
- DNA sample
- binding buffer
- magnetic beads

Steps:
1. Prepare 8 DNA cleanup wells in a 96-well plate.
2. Add 20 uL DNA sample to each well.
3. Add 80 uL binding buffer to each well.
4. Add 20 uL magnetic beads to each well.
5. Mix each well thoroughly 5 times.
""",
    ),
    ProtocolCase(
        "cell_culture_media_exchange",
        "Cell culture media exchange",
        """
Cell Culture Plate Media Exchange

Materials:
- cell culture samples
- fresh media
- PBS buffer

Steps:
1. Prepare 6 wells containing adherent cells in a 96-well plate.
2. Add 50 uL PBS buffer to each well.
3. Add 100 uL fresh media to each well.
4. Mix gently without disturbing cells.
""",
    ),
]


def get_cases(limit: int | None = None) -> list[ProtocolCase]:
    return CASES if limit is None else CASES[:limit]
