from __future__ import annotations

from enum import Enum


class DecisionCode(str, Enum):
    D001 = "Exact Variant"
    D002 = "Dictionary Match"
    D003 = "Pattern Match"
    D004 = "Synonym Match"
    D005 = "Fuzzy Match"
    D006 = "Manual Rule"
    D007 = "Shadow CMCC"

    D101 = "Parser Reject"
    D102 = "OCR Reject"
    D103 = "Header Missing"
    D104 = "Column Mapping Failed"
    D105 = "Layout Unknown"
    D106 = "Low Parser Confidence"
    D107 = "Low Document Confidence"

    D201 = "Unknown Variant"
    D202 = "Unknown Pattern"
    D203 = "Unknown Concept"
    D204 = "Multiple Candidates"

    def describe(self) -> str:
        return self.value


class TraceStage(str, Enum):
    PARSER = "Parser"
    NORMALIZATION = "Normalization"
    CANDIDATE_VALIDATOR = "Candidate Validator"
    PARSER_QUALITY = "Parser Quality"
    CMCC = "CMCC"
    DICTIONARY = "Dictionary"
    LEARNING = "Learning Engine"
    OFFICIAL_CLASSIFICATION = "Official Classification"
    SHADOW = "Shadow"
    FINAL = "Final Decision"
