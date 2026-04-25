"""
Pydantic schemas for ProtocolIR pipeline.
Defines strict type contracts between each layer.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from enum import Enum


class ReagentClass(str, Enum):
    """Allowed reagent classifications."""
    TEMPLATE = "template"
    MASTER_MIX = "master_mix"
    PRIMER = "primer"
    WATER = "water"
    BUFFER = "buffer"
    ENZYME = "enzyme"
    DYE = "dye"
    SALT = "salt"
    UNKNOWN = "unknown"


class Material(BaseModel):
    """A reagent/material used in the protocol."""
    name: str = Field(..., description="Name of the reagent")
    reagent_class: ReagentClass = Field(..., description="Classification of reagent")
    volume_ul: Optional[float] = Field(None, description="Estimated volume needed in µL")
    notes: Optional[str] = None


class SemanticActionType(str, Enum):
    """Types of semantic actions in a protocol."""
    TRANSFER = "transfer"
    MIX = "mix"
    DELAY = "delay"
    TEMPERATURE = "temperature"
    CENTRIFUGE = "centrifuge"
    VORTEX = "vortex"
    INCUBATE = "incubate"
    COMMENT = "comment"


class SemanticAction(BaseModel):
    """A semantic action extracted from natural language."""
    action_type: SemanticActionType
    reagent: Optional[str] = Field(None, description="Reagent involved")
    volume_ul: Optional[float] = Field(None, description="Volume in µL")
    source_hint: Optional[str] = Field(None, description="Source location hint (e.g., 'DNA template tube')")
    destination_hint: Optional[str] = Field(None, description="Destination location hint")
    repetitions: Optional[int] = None
    constraints: List[str] = Field(default_factory=list, description="Physical constraints (e.g., 'keep on ice')")
    description: str = Field("", description="Original text from protocol")


class ParsedProtocol(BaseModel):
    """Output of semantic parser layer."""
    goal: str = Field(..., description="One-liner of what the protocol achieves")
    source: Optional[str] = None
    materials: List[Material]
    actions: List[SemanticAction]
    ambiguities: List[str] = Field(default_factory=list, description="Missing details flagged during parsing")


class GroundedAction(BaseModel):
    """Action with resolved deck locations."""
    action_type: SemanticActionType
    reagent: Optional[str] = None
    volume_ul: Optional[float] = None
    source: Optional[str] = Field(None, description="Resolved source location (e.g., 'template_rack/A1')")
    destination: Optional[str] = Field(None, description="Resolved destination location")
    repetitions: Optional[int] = None
    constraints: List[str] = Field(default_factory=list)
    source_location_type: Optional[str] = None
    dest_location_type: Optional[str] = None


class LabwareSpec(BaseModel):
    """Labware specification."""
    name: str
    opentrons_name: str = Field(..., description="Name in Opentrons API")
    slot: int
    alias: str
    max_volume_ul: float
    well_count: int
    well_volume_ul: Optional[List[float]] = None


class InstrumentSpec(BaseModel):
    """Instrument specification."""
    name: str
    opentrons_name: str
    mount: Literal["left", "right"]
    min_volume_ul: float
    max_volume_ul: float
    tipracks: List[str] = Field(..., description="List of tiprack aliases")


class IROpType(str, Enum):
    """Types of IR operations."""
    LOAD_LABWARE = "LoadLabware"
    LOAD_INSTRUMENT = "LoadInstrument"
    PICK_UP_TIP = "PickUpTip"
    DROP_TIP = "DropTip"
    ASPIRATE = "Aspirate"
    DISPENSE = "Dispense"
    MIX = "Mix"
    DELAY = "Delay"
    SET_TEMPERATURE = "SetTemperature"
    INCUBATE = "Incubate"
    CENTRIFUGE = "Centrifuge"


class IROp(BaseModel):
    """Single IR operation - machine-readable lab instruction."""
    op: IROpType

    # LoadLabware / LoadInstrument fields
    name: Optional[str] = None
    opentrons_name: Optional[str] = None
    slot: Optional[int] = None
    alias: Optional[str] = None
    mount: Optional[Literal["left", "right"]] = None
    tipracks: Optional[List[str]] = None

    # Instrument specs
    min_volume: Optional[float] = None
    max_volume: Optional[float] = None

    # Labware specs
    max_volume_ul: Optional[float] = None
    well_count: Optional[int] = None

    # Aspirate/Dispense/Mix fields
    pipette: Optional[str] = None
    volume_ul: Optional[float] = None
    source: Optional[str] = Field(None, description="Source well (e.g., 'template_rack/A1')")
    destination: Optional[str] = Field(None, description="Destination well")
    location: Optional[str] = None
    reagent: Optional[str] = None
    repetitions: Optional[int] = None

    # Other
    delay_seconds: Optional[float] = None
    temperature_c: Optional[float] = None


class Violation(BaseModel):
    """Safety violation detected during verification."""
    violation_type: str = Field(..., description="Type of violation")
    severity: Literal["CRITICAL", "WARNING", "INFO"] = "WARNING"
    action_idx: int = Field(..., description="Index of IR operation that caused violation")
    message: str = Field(..., description="Human-readable description")
    suggested_fix: Optional[str] = None


class TrajectoryFeatures(BaseModel):
    """Extracted features for reward scoring."""
    contamination_violations: int = 0
    pipette_range_violations: int = 0
    well_overflow_violations: int = 0
    aspirate_no_tip_violations: int = 0
    dispense_no_tip_violations: int = 0
    unknown_location_violations: int = 0
    drop_tip_with_liquid_violations: int = 0
    total_violations: int = 0

    tip_changes: int = 0
    transfer_count: int = 0
    mix_events: int = 0
    aspirate_events: int = 0
    dispense_events: int = 0

    tip_changed_between_different_reagents: int = 0
    complete_transfer_pairs: int = 0
    missing_mix_events: int = 0


class RewardScore(BaseModel):
    """Reward score and breakdown."""
    total_score: float
    feature_scores: Dict[str, float] = Field(default_factory=dict)
    violations_count: int = 0
    threshold_passed: bool = False


class SimulationResult(BaseModel):
    """Result of Opentrons simulator validation."""
    passed: bool
    command_count: int = 0
    aspirate_count: int = 0
    dispense_count: int = 0
    tip_count: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    log: Optional[str] = None


class ProtocolPipeline(BaseModel):
    """Complete state through the pipeline."""
    raw_text: str
    source_url: Optional[str] = None

    parsed: Optional[ParsedProtocol] = None
    grounded: Optional[List[GroundedAction]] = None

    ir_original: Optional[List[IROp]] = None
    ir_repaired: Optional[List[IROp]] = None

    violations: List[Violation] = Field(default_factory=list)
    repairs_applied: List[str] = Field(default_factory=list)

    reward_before: float = 0.0
    reward_after: float = 0.0
    reward_score: Optional[RewardScore] = None

    generated_script: Optional[str] = None
    simulation_result: Optional[SimulationResult] = None

    audit_report: Optional[str] = None

    human_escalations: List[str] = Field(default_factory=list)
