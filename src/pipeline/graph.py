"""Pipeline state definition and LangGraph construction."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Annotated, TypedDict

from langgraph.graph import StateGraph, END

from ..parser.cobol_parser import ParsedCobolProgram
from ..converter.code_converter import ConversionResult, GeneratedFile
from ..analyzer.accuracy_analyzer import AccuracyReport
from ..llm_providers import LLMProvider
from ..core.logging import get_logger
from config.settings import settings

logger = get_logger("pipeline")


class PipelineState(TypedDict, total=False):
    """State flowing through the LangGraph pipeline.
    
    Each node reads/writes specific keys. LangGraph handles state transitions.
    """
    # Inputs
    source_file: str
    source_code: str
    
    # Parse phase
    parsed_program: ParsedCobolProgram
    is_large_file: bool
    estimated_tokens: int
    
    # Conversion phase
    conversion_result: ConversionResult
    
    # Analysis phase
    accuracy_report: AccuracyReport
    iteration: int
    iteration_history: list
    
    # Control flow
    status: str  # "converting", "analyzing", "refining", "complete", "failed"
    error: str
    
    # Metrics
    total_tokens: int
    start_time: float


class MigrationPipeline:
    """LangGraph-based migration pipeline with iterative refinement.
    
    Constructs and executes a state machine:
        parse → convert → analyze → decide
                                      ↓ (if passed)
                                    complete
                                      ↓ (if not passed & iterations left)
                                    refine → analyze → decide ...
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_iterations: int = None,
        target_accuracy: float = None,
        output_dir: Path = None,
    ):
        self.llm = llm_provider
        self.max_iterations = max_iterations or settings.pipeline.max_iterations
        self.target_accuracy = target_accuracy or settings.pipeline.target_accuracy
        self.output_dir = output_dir or settings.output_dir
        
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph state machine."""
        from .nodes import (
            parse_source,
            convert_code,
            analyze_accuracy,
            refine_code,
            decide_next,
        )
        
        graph = StateGraph(PipelineState)
        
        # Add nodes
        graph.add_node("parse", lambda state: parse_source(state, self.llm))
        graph.add_node("convert", lambda state: convert_code(state, self.llm))
        graph.add_node("analyze", lambda state: analyze_accuracy(state, self.llm))
        graph.add_node("refine", lambda state: refine_code(state, self.llm))
        
        # Define edges
        graph.set_entry_point("parse")
        graph.add_edge("parse", "convert")
        graph.add_edge("convert", "analyze")
        
        # Conditional edge after analysis
        graph.add_conditional_edges(
            "analyze",
            lambda state: decide_next(state, self.max_iterations),
            {
                "complete": END,
                "refine": "refine",
                "failed": END,
            },
        )
        
        # After refinement, analyze again
        graph.add_edge("refine", "analyze")
        
        return graph.compile()

    def run(self, source_file: Path) -> PipelineState:
        """Execute the migration pipeline.
        
        Args:
            source_file: Path to the COBOL/Telon source file
            
        Returns:
            Final pipeline state with all results
        """
        source_code = source_file.read_text(encoding="utf-8", errors="replace")
        
        initial_state: PipelineState = {
            "source_file": str(source_file),
            "source_code": source_code,
            "iteration": 0,
            "iteration_history": [],
            "total_tokens": 0,
            "start_time": time.time(),
            "status": "converting",
            "error": "",
        }
        
        logger.info(
            "pipeline_started",
            source_file=str(source_file),
            source_size=len(source_code),
            max_iterations=self.max_iterations,
        )
        
        # Execute the graph
        final_state = self._graph.invoke(initial_state)
        
        elapsed = time.time() - final_state.get("start_time", time.time())
        logger.info(
            "pipeline_completed",
            status=final_state.get("status"),
            iterations=final_state.get("iteration"),
            total_tokens=final_state.get("total_tokens"),
            elapsed_seconds=round(elapsed, 1),
        )
        
        return final_state
