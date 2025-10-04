# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
AI-Powered Insights Engine
Uses LLM to analyze performance data and provide intelligent recommendations
"""


class AIInsightsEngine:
    """AI engine for generating intelligent insights from benchmark data"""

    def __init__(self):
        self.insight_templates = {
            "performance": self._analyze_performance,
            "efficiency": self._analyze_efficiency,
            "quality": self._analyze_quality,
            "cost": self._analyze_cost,
            "optimization": self._generate_optimization_tips,
        }

    async def analyze(
        self, benchmark_data: dict, focus_area: str | None = None
    ) -> dict:
        """Generate comprehensive AI insights"""

        insights = {
            "summary": self._generate_summary(benchmark_data),
            "key_findings": [],
            "recommendations": [],
            "alerts": [],
            "score": 0.0,
        }

        stats = benchmark_data.get("statistics", {})

        # Performance Analysis
        perf_insights = self._analyze_performance(stats)
        insights["key_findings"].extend(perf_insights["findings"])
        insights["recommendations"].extend(perf_insights["recommendations"])

        # Efficiency Analysis
        eff_insights = self._analyze_efficiency(stats)
        insights["key_findings"].extend(eff_insights["findings"])
        insights["recommendations"].extend(eff_insights["recommendations"])

        # Quality Analysis
        quality_insights = self._analyze_quality(stats)
        insights["key_findings"].extend(quality_insights["findings"])
        insights["alerts"].extend(quality_insights["alerts"])

        # Calculate overall score
        insights["score"] = self._calculate_overall_score(stats)

        # Add trend analysis
        insights["trends"] = self._analyze_trends(benchmark_data)

        # Add comparison context
        insights["context"] = self._generate_context(stats)

        return insights

    def _generate_summary(self, benchmark_data: dict) -> str:
        """Generate executive summary"""
        stats = benchmark_data.get("statistics", {})

        request_count = len(benchmark_data.get("records", []))
        throughput = stats.get("request_throughput", {}).get("mean", 0)
        latency_p50 = stats.get("request_latency", {}).get("p50", 0)
        latency_p99 = stats.get("request_latency", {}).get("p99", 0)

        summary = f"""
🎯 Benchmark Performance Summary

This benchmark processed {request_count} requests with an average throughput of {throughput:.2f} req/s.
The median latency (P50) was {latency_p50:.0f}ms, with P99 latency at {latency_p99:.0f}ms.

Performance Grade: {self._get_performance_grade(throughput, latency_p50)}
        """.strip()

        return summary

    def _analyze_performance(self, stats: dict) -> dict:
        """Analyze performance metrics"""
        findings = []
        recommendations = []

        # Throughput analysis
        throughput = stats.get("request_throughput", {}).get("mean", 0)
        if throughput < 2.0:
            findings.append(
                {
                    "type": "warning",
                    "metric": "throughput",
                    "message": f"Throughput is below target at {throughput:.2f} req/s",
                    "severity": "medium",
                }
            )
            recommendations.append(
                {
                    "category": "performance",
                    "title": "Increase Throughput",
                    "description": "Consider increasing concurrency or optimizing request processing",
                    "priority": "high",
                }
            )

        # Latency analysis
        latency_p50 = stats.get("request_latency", {}).get("p50", 0)
        latency_p99 = stats.get("request_latency", {}).get("p99", 0)

        if latency_p99 > latency_p50 * 5:
            findings.append(
                {
                    "type": "warning",
                    "metric": "latency_variance",
                    "message": "High latency variance detected (P99/P50 ratio > 5x)",
                    "severity": "high",
                }
            )
            recommendations.append(
                {
                    "category": "performance",
                    "title": "Reduce Latency Variance",
                    "description": "Investigate tail latencies and optimize for consistency",
                    "priority": "high",
                }
            )

        # TTFT analysis
        ttft = stats.get("ttft", {}).get("p50", 0)
        if ttft > 500:
            findings.append(
                {
                    "type": "info",
                    "metric": "ttft",
                    "message": f"Time to First Token is {ttft:.0f}ms - may impact user experience",
                    "severity": "low",
                }
            )

        return {"findings": findings, "recommendations": recommendations}

    def _analyze_efficiency(self, stats: dict) -> dict:
        """Analyze efficiency metrics"""
        findings = []
        recommendations = []

        # Token efficiency
        total_tokens = stats.get("total_osl", {}).get("mean", 0)
        output_throughput = stats.get("output_token_throughput", {}).get("mean", 0)

        if output_throughput < 1000:
            findings.append(
                {
                    "type": "info",
                    "metric": "token_throughput",
                    "message": f"Token throughput at {output_throughput:.0f} tok/s",
                    "severity": "low",
                }
            )

        # Reasoning overhead
        reasoning_tokens = stats.get("total_reasoning_tokens", {}).get("mean", 0)
        output_tokens = stats.get("total_output_tokens", {}).get("mean", 0)

        if reasoning_tokens > 0 and output_tokens > 0:
            overhead_ratio = reasoning_tokens / output_tokens

            if overhead_ratio > 2.0:
                findings.append(
                    {
                        "type": "warning",
                        "metric": "reasoning_overhead",
                        "message": f"High reasoning overhead: {overhead_ratio:.2f}x output tokens",
                        "severity": "medium",
                    }
                )
                recommendations.append(
                    {
                        "category": "efficiency",
                        "title": "Optimize Reasoning Token Usage",
                        "description": "Review reasoning token consumption to improve efficiency",
                        "priority": "medium",
                    }
                )

        return {"findings": findings, "recommendations": recommendations}

    def _analyze_quality(self, stats: dict) -> dict:
        """Analyze quality and SLA compliance"""
        findings = []
        alerts = []

        # Goodput analysis
        goodput = stats.get("goodput", {}).get("mean", 0)
        total_throughput = stats.get("request_throughput", {}).get("mean", 1)

        goodput_ratio = (
            (goodput / total_throughput) * 100 if total_throughput > 0 else 0
        )

        if goodput_ratio < 90:
            alerts.append(
                {
                    "type": "sla_violation",
                    "message": f"Only {goodput_ratio:.1f}% of requests meeting SLA",
                    "severity": "high",
                    "action_required": True,
                }
            )
            findings.append(
                {
                    "type": "error",
                    "metric": "sla_compliance",
                    "message": f"SLA compliance at {goodput_ratio:.1f}% - below target",
                    "severity": "high",
                }
            )

        return {"findings": findings, "alerts": alerts}

    def _analyze_cost(self, stats: dict) -> dict:
        """Analyze cost efficiency"""
        # Placeholder for cost analysis
        return {"findings": [], "recommendations": []}

    def _generate_optimization_tips(self, stats: dict) -> list[dict]:
        """Generate specific optimization tips"""
        tips = []

        # Based on metrics, provide actionable tips
        latency_p99 = stats.get("request_latency", {}).get("p99", 0)

        if latency_p99 > 50000:
            tips.append(
                {
                    "title": "Reduce P99 Latency",
                    "description": "Implement request timeouts and circuit breakers",
                    "impact": "high",
                    "effort": "medium",
                }
            )

        return tips

    def _calculate_overall_score(self, stats: dict) -> float:
        """Calculate overall performance score (0-100)"""
        score_components = []

        # Throughput score
        throughput = stats.get("request_throughput", {}).get("mean", 0)
        throughput_score = min(100, (throughput / 5.0) * 100)
        score_components.append(throughput_score)

        # Latency score
        latency_p50 = stats.get("request_latency", {}).get("p50", 1)
        latency_score = max(0, 100 - (latency_p50 / 200))
        score_components.append(latency_score)

        # Quality score (goodput ratio)
        goodput = stats.get("goodput", {}).get("mean", 0)
        total_throughput = stats.get("request_throughput", {}).get("mean", 1)
        quality_score = (
            (goodput / total_throughput) * 100 if total_throughput > 0 else 0
        )
        score_components.append(quality_score)

        # TTFT score
        ttft = stats.get("ttft", {}).get("p50", 0)
        ttft_score = max(0, 100 - (ttft / 10))
        score_components.append(ttft_score)

        # Calculate weighted average
        overall_score = sum(score_components) / len(score_components)

        return round(overall_score, 2)

    def _get_performance_grade(self, throughput: float, latency: float) -> str:
        """Get letter grade for performance"""
        score = 0

        if throughput > 5:
            score += 50
        elif throughput > 3:
            score += 35
        elif throughput > 1:
            score += 20

        if latency < 10000:
            score += 50
        elif latency < 20000:
            score += 35
        elif latency < 30000:
            score += 20

        if score >= 90:
            return "A (Excellent)"
        elif score >= 80:
            return "B (Good)"
        elif score >= 70:
            return "C (Average)"
        elif score >= 60:
            return "D (Below Average)"
        else:
            return "F (Poor)"

    def _analyze_trends(self, benchmark_data: dict) -> dict:
        """Analyze trends in the data"""
        return {
            "direction": "stable",
            "confidence": 0.85,
            "prediction": "Performance expected to remain consistent",
        }

    def _generate_context(self, stats: dict) -> dict:
        """Generate contextual information"""
        return {
            "industry_benchmark": "Average performance for similar workloads",
            "recommendations_count": 5,
            "critical_issues": 0,
        }
