"""
LLM Evaluation Framework — quality monitoring for agent responses.

Provides hallucination detection, answer quality scoring, and
evaluation harness for continuous monitoring of LLM outputs.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


class EvalResult(BaseModel):
    """Result of a single evaluation."""

    metric_name: str
    score: float = Field(ge=0, le=1, description="Score from 0 to 1")
    details: str = Field(default="", description="Evaluation details")
    passed: bool = Field(description="Whether the check passed")


class EvalReport(BaseModel):
    """Comprehensive evaluation report for a single response."""

    query: str
    response: str
    agent: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    results: list[EvalResult] = Field(default_factory=list)
    overall_score: float = Field(default=0.0, ge=0, le=1)
    passed: bool = Field(default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def calculate_overall(self) -> None:
        """Calculate overall score from individual results."""
        if self.results:
            self.overall_score = sum(r.score for r in self.results) / len(self.results)
            self.passed = all(r.passed for r in self.results)


class HallucinationDetector:
    """
    Detects potential hallucinations in LLM responses.

    Checks if the response contains claims not supported by context.
    """

    def __init__(self, threshold: float = 0.6) -> None:
        self._threshold = threshold

    async def evaluate(
        self,
        query: str,
        response: str,
        context: str = "",
        sources: list[str] | None = None,
    ) -> EvalResult:
        """
        Evaluate response for hallucination risk.

        Args:
            query: Original user query
            response: LLM response to evaluate
            context: RAG context used to generate response
            sources: Source references cited in response

        Returns:
            EvalResult with hallucination score.
        """
        score = 1.0
        details = []

        # Check 1: Response references sources when context is provided
        if context and sources:
            if not sources:
                score -= 0.3
                details.append("Response has context but no source citations")
        elif context and not sources:
            score -= 0.2
            details.append("Context provided but no sources cited")

        # Check 2: Response length vs query complexity
        if len(response) < 10 and len(query) > 20:
            score -= 0.2
            details.append("Response suspiciously short for complex query")

        # Check 3: Arabic language consistency (if query is Arabic)
        arabic_chars = sum(1 for c in query if '\u0600' <= c <= '\u06FF')
        if arabic_chars > len(query) * 0.3:
            response_arabic = sum(1 for c in response if '\u0600' <= c <= '\u06FF')
            if response_arabic < len(response) * 0.1:
                score -= 0.2
                details.append("Query is Arabic but response is mostly non-Arabic")

        # Check 4: No fabrication of specific numbers without context
        import re
        numbers_in_response = re.findall(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?', response)
        if numbers_in_response and not context:
            score -= 0.15
            details.append("Response contains specific numbers without context")

        score = max(0.0, score)
        passed = score >= self._threshold

        if not passed:
            logger.warning(
                "eval.hallucination_risk",
                query=query[:100],
                score=score,
                details=details,
            )

        return EvalResult(
            metric_name="hallucination",
            score=score,
            details="; ".join(details) if details else "No hallucination indicators found",
            passed=passed,
        )


class AnswerQualityScorer:
    """
    Scores the quality of LLM responses based on multiple criteria.
    """

    def __init__(self) -> None:
        pass

    async def evaluate(
        self,
        query: str,
        response: str,
        agent: str,
    ) -> EvalResult:
        """
        Evaluate response quality.

        Args:
            query: Original user query
            response: LLM response
            agent: Which agent handled the request

        Returns:
            EvalResult with quality score.
        """
        score = 1.0
        details = []

        # Check 1: Response is not empty
        if not response or not response.strip():
            return EvalResult(
                metric_name="quality",
                score=0.0,
                details="Empty response",
                passed=False,
            )

        # Check 2: Response length is reasonable
        if len(response) < 5:
            score -= 0.3
            details.append("Response too short")
        elif len(response) > 5000:
            score -= 0.1
            details.append("Response unusually long")

        # Check 3: Response addresses the query
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        overlap = len(query_words & response_words)
        if len(query_words) > 3 and overlap < 1:
            score -= 0.2
            details.append("Response may not address the query")

        # Check 4: No error messages in successful response
        error_indicators = ["error", "exception", "traceback", "failed"]
        if any(ind in response.lower() for ind in error_indicators):
            if agent != "general":  # General agent may explain errors
                score -= 0.3
                details.append("Response contains error indicators")

        # Check 5: Arabic language consistency for Arabic queries
        import re
        arabic_chars = sum(1 for c in query if '\u0600' <= c <= '\u06FF')
        if arabic_chars > len(query) * 0.3:
            response_arabic = sum(1 for c in response if '\u0600' <= c <= '\u06FF')
            if response_arabic < len(response) * 0.2:
                score -= 0.15
                details.append("Arabic query but response not in Arabic")

        score = max(0.0, score)
        passed = score >= 0.5

        return EvalResult(
            metric_name="quality",
            score=score,
            details="; ".join(details) if details else "Response quality is good",
            passed=passed,
        )


class EvalHarness:
    """
    Evaluation harness for continuous LLM quality monitoring.

    Runs multiple evaluations on each response and produces a report.
    """

    def __init__(
        self,
        hallucination_threshold: float = 0.6,
    ) -> None:
        self._hallucination_detector = HallucinationDetector(hallucination_threshold)
        self._quality_scorer = AnswerQualityScorer()
        self._reports: list[EvalReport] = []

    async def evaluate(
        self,
        query: str,
        response: str,
        agent: str,
        context: str = "",
        sources: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvalReport:
        """
        Run all evaluations on a response.

        Args:
            query: Original user query
            response: LLM response to evaluate
            agent: Which agent handled the request
            context: RAG context used
            sources: Source references
            metadata: Additional metadata

        Returns:
            EvalReport with all evaluation results.
        """
        report = EvalReport(
            query=query,
            response=response,
            agent=agent,
            metadata=metadata or {},
        )

        # Run evaluations
        hallucination_result = await self._hallucination_detector.evaluate(
            query, response, context, sources
        )
        quality_result = await self._quality_scorer.evaluate(query, response, agent)

        report.results = [hallucination_result, quality_result]
        report.calculate_overall()

        # Store report
        self._reports.append(report)

        # Log if below threshold
        if not report.passed:
            logger.warning(
                "eval.response_failed",
                query=query[:100],
                agent=agent,
                overall_score=report.overall_score,
                results=[f"{r.metric_name}:{r.score:.2f}" for r in report.results],
            )

        return report

    def get_stats(self, last_n: int = 100) -> dict[str, Any]:
        """
        Get evaluation statistics.

        Args:
            last_n: Number of recent reports to analyze

        Returns:
            Statistics dictionary.
        """
        recent = self._reports[-last_n:] if self._reports else []

        if not recent:
            return {"total": 0, "pass_rate": 0, "avg_score": 0}

        passed = sum(1 for r in recent if r.passed)
        avg_score = sum(r.overall_score for r in recent) / len(recent)

        return {
            "total": len(recent),
            "passed": passed,
            "failed": len(recent) - passed,
            "pass_rate": passed / len(recent),
            "avg_score": avg_score,
        }
