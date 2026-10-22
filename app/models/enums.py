from enum import StrEnum


class DataReviewStatus(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"


class TreeStatus(StrEnum):
    AWAITING_PLANTING = "awaiting_planting"
    PLANTED = "planted"
    ATTENTION = "attention"
    DEAD = "dead"


class CareEventType(StrEnum):
    WATERING = "watering"
    FERTILIZING = "fertilizing"
    PRUNING = "pruning"
    OTHER = "other"


class EventSource(StrEnum):
    PUBLIC = "public"
    ADMIN = "admin"


class RainSource(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class WateringPhase(StrEnum):
    NEWLY_PLANTED = "newly_planted"
    ESTABLISHED = "established"


# pt-BR labels for the UI. Code and database stay in English.
TREE_STATUS_LABELS = {
    TreeStatus.AWAITING_PLANTING: "Aguardando plantio",
    TreeStatus.PLANTED: "Plantada",
    TreeStatus.ATTENTION: "Atenção",
    TreeStatus.DEAD: "Morta",
}
CARE_EVENT_LABELS = {
    CareEventType.WATERING: "Rega",
    CareEventType.FERTILIZING: "Adubação",
    CareEventType.PRUNING: "Poda",
    CareEventType.OTHER: "Outro",
}
