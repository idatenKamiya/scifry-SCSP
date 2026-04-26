"""Typed contracts for the ProtocolIR compiler pipeline."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model that keeps layer boundaries explicit."""

    model_config = ConfigDict(extra="forbid")


class ReagentClass(str, Enum):
    TEMPLATE = "template"
    MASTER_MIX = "master_mix"
    PRIMER = "primer"
    WATER = "water"
    BUFFER = "buffer"
    ENZYME = "enzyme"
    DYE = "dye"
    SALT = "salt"
    UNKNOWN = "unknown"


class Material(StrictModel):
    name: str = Field(..., description="Human-readable reagent or material name.")
    reagent_class: ReagentClass = ReagentClass.UNKNOWN
    volume_ul: Optional[float] = Field(None, description="Estimated total volume needed.")
    location_hint: Optional[str] = None
    notes: Optional[str] = None


class SemanticActionType(str, Enum):
    TRANSFER = "transfer"
    MIX = "mix"
    DELAY = "delay"
    TEMPERATURE = "temperature"
    CENTRIFUGE = "centrifuge"
    VORTEX = "vortex"
    INCUBATE = "incubate"
    COMMENT = "comment"


class SemanticAction(StrictModel):
    action_type: SemanticActionType
    reagent: Optional[str] = None
    volume_ul: Optional[float] = None
    source_hint: Optional[str] = None
    destination_hint: Optional[str] = None
    repetitions: Optional[int] = None
    constraints: List[str] = Field(default_factory=list)
    description: str = ""


class ParsedProtocol(StrictModel):
    goal: str
    source: Optional[str] = None
    title: Optional[str] = None
    parser_backend: str = "unknown"
    sample_count: int = Field(8, ge=1, le=96)
    materials: List[Material] = Field(default_factory=list)
    actions: List[SemanticAction] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)


class GroundedAction(StrictModel):
    action_type: SemanticActionType
    reagent: Optional[str] = None
    volume_ul: Optional[float] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    destinations: List[str] = Field(default_factory=list)
    repetitions: Optional[int] = None
    constraints: List[str] = Field(default_factory=list)
    source_location_type: Optional[str] = None
    dest_location_type: Optional[str] = None


class LabwareSpec(StrictModel):
    name: str
    opentrons_name: str
    slot: int
    alias: str
    max_volume_ul: float
    well_count: int


class InstrumentSpec(StrictModel):
    name: str
    opentrons_name: str
    mount: Literal["left", "right"]
    min_volume_ul: float
    max_volume_ul: float
    tipracks: List[str]


class IROpType(str, Enum):
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
    COMMENT = "Comment"


class IROp(StrictModel):
    op: IROpType

    # LoadLabware / LoadInstrument fields.
    name: Optional[str] = None
    opentrons_name: Optional[str] = None
    slot: Optional[int] = None
    alias: Optional[str] = None
    mount: Optional[Literal["left", "right"]] = None
    tipracks: Optional[List[str]] = None
    min_volume: Optional[float] = None
    max_volume: Optional[float] = None
    max_volume_ul: Optional[float] = None
    well_count: Optional[int] = None

    # Liquid-handling fields.
    pipette: Optional[str] = None
    volume_ul: Optional[float] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    location: Optional[str] = None
    reagent: Optional[str] = None
    repetitions: Optional[int] = None

    # Timing / module fields.
    delay_seconds: Optional[float] = None
    temperature_c: Optional[float] = None
    comment: Optional[str] = None


class Violation(StrictModel):
    violation_type: str
    severity: Literal["CRITICAL", "WARNING", "INFO"] = "WARNING"
    action_idx: int
    message: str
    suggested_fix: Optional[str] = None
    repairable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class TrajectoryFeatures(StrictModel):
    contamination_violations: int = 0
    pipette_range_violations: int = 0
    well_overflow_violations: int = 0
    aspirate_no_tip_violations: int = 0
    dispense_no_tip_violations: int = 0
    mix_no_tip_violations: int = 0
    unknown_location_violations: int = 0
    invalid_location_violations: int = 0
    drop_tip_with_liquid_violations: int = 0
    missing_mix_events: int = 0

    tip_changes: int = 0
    mix_events: int = 0
    aspirate_events: int = 0
    dispense_events: int = 0
    total_operations: int = 0

    tip_changed_between_different_reagents: int = 0
    complete_transfer_pairs: int = 0


class RewardScore(StrictModel):
    total_score: float
    feature_scores: Dict[str, float] = Field(default_factory=dict)
    violations_count: int = 0
    threshold_passed: bool = False


class SimulationResult(StrictModel):
    passed: bool
    command_count: int = 0
    aspirate_count: int = 0
    dispense_count: int = 0
    tip_count: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    log: Optional[str] = None
    used_real_simulator: bool = False


class ProtocolPipeline(StrictModel):
    raw_text: str
    source_url: Optional[str] = None
    deck_layout: Dict[str, Any] = Field(default_factory=dict)

    parsed: Optional[ParsedProtocol] = None
    grounded: Optional[List[GroundedAction]] = None

    ir_original: Optional[List[IROp]] = None
    ir_repaired: Optional[List[IROp]] = None

    violations: List[Violation] = Field(default_factory=list)
    violations_before_repair: List[Violation] = Field(default_factory=list)
    violations_after_repair: List[Violation] = Field(default_factory=list)
    repairs_applied: List[str] = Field(default_factory=list)

    reward_before: float = 0.0
    reward_after: float = 0.0
    reward_score: Optional[RewardScore] = None

    generated_script: Optional[str] = None
    simulation_result: Optional[SimulationResult] = None

    audit_report: Optional[str] = None
    human_escalations: List[str] = Field(default_factory=list)
